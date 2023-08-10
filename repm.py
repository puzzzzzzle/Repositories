#!/usr/bin/env python3
import configparser
import argparse
import inspect
import logging
import functools
import os
import pathlib
import re
import subprocess

# ---------- logger ----------
logging.basicConfig(level=logging.DEBUG,
                    format='|%(asctime)s|%(name)s|%(levelname)s|%(message)s| %(pathname)s:%(lineno)d ',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)


# ---------- common cmd mng define ----------
def get_param_description(function, para_name):
    """
    get para's comment
    """
    docstring = function.__doc__
    if not docstring:
        return ""

    # regex for para
    pattern = rf":param\s*{para_name}\s*:\s*(.+)\s*"
    regex = re.compile(pattern, re.MULTILINE)
    match = regex.search(docstring)

    if match:
        param_desc = match.groups()
        return f"{param_desc[0]}"
    else:
        return ""


def build_args(sub_cmds, cls):
    """
    build args for parser by function define
    """

    class MyHelpFormatter(argparse.ArgumentDefaultsHelpFormatter):
        def _format_args(self, action, default_metavar):
            return action.metavar

    parser = sub_cmds.add_parser(cls.cmd, description=cls.description,
                                 help=cls.help, formatter_class=MyHelpFormatter)

    run_func = getattr(cls, "run")
    args, varargs, varkw, defaults, kwonlyargs, kwonlydefaults, annotations = inspect.getfullargspec(run_func)
    default_arg_start = len(args)
    if defaults is not None:
        default_arg_start = len(args) - len(defaults)

    # add args
    normal_args = []
    default_args = {}
    for i in range(len(args)):
        if i == 0:
            continue
        arg = args[i]
        if i >= default_arg_start:
            default = defaults[i - default_arg_start]
            default_args[arg] = default
        else:
            normal_args.append(arg)
    # add positional requires args
    cls.normal_args = normal_args
    cls.default_args = default_args
    cls.annotations = annotations
    if len(normal_args) > 0:
        normal_args_help = ""
        metavar_str = ""
        for arg in normal_args:
            metavar_str += f"{arg} "
            t = str
            if arg in annotations:
                t = annotations[arg]
            comment = get_param_description(run_func, arg)
            if comment != "":
                comment = ":" + comment
            normal_args_help += f"[{arg}({t.__name__}){comment}] "
        parser.add_argument("args", metavar=metavar_str, type=str, nargs=len(normal_args),
                            help=normal_args_help)
    # add default args
    if len(default_args) > 0:
        for arg, value in default_args.items():
            if arg in annotations:
                t = annotations[arg]
            elif value is not None:
                t = type(value)
            else:
                t = str
            name = f"--{arg}"
            if len(arg) == 1:
                name = f"-{arg}"
            paras = {"type": t, "default": value}
            if t == bool:
                del paras["type"]
                help_str = f"{get_param_description(run_func, arg)}"
                if value:
                    help_str += f", default is set, add flags to set false"
                    paras["action"] = "store_false"
                else:
                    help_str += f", default is not set, add flags to set true"
                    paras["action"] = "store_true"

                paras["help"] = help_str
            else:
                help_str = f"{get_param_description(run_func, arg)}"
                paras["help"] = help_str

            parser.add_argument(name, **paras)

    parser.set_defaults(func=functools.partial(run_cmd, cls))
    pass


def run_cmd(cls, para):
    """
    execute cls
    """
    normal_args = cls.normal_args
    default_args = cls.default_args
    annotations = cls.annotations
    logger.debug(f"run {cls.__name__} {para}")
    # normal args
    if len(normal_args) > 0:
        args = list(para.args)
        assert len(args) == len(normal_args)
        for i in range(len(normal_args)):
            arg_name = normal_args[i]
            if arg_name in annotations:
                arg_type = annotations[arg_name]
                logger.debug(f"trans type {arg_name} -> {arg_type}; str value: {args[i]} ")
                args[i] = arg_type(args[i])
        args = tuple(args)
        logger.debug(f"position args {args}")
    else:
        args = ()
    # default args
    if len(default_args) > 0:
        dargs = dict(default_args)
        for key in default_args.keys():
            attr = getattr(para, key)
            logger.debug(f"get {key} {attr}")
            dargs[key] = attr
        logger.debug(f"default args {dargs}")
    else:
        dargs = {}
    cls.run_cmd(cls, *args, **dargs)
    pass


# ---------- repositories mng base define ----------
CONFIG_FILE_NAME = "Repositories.ini"


def cmd_main(args=None):
    """
    main args builder
    :return:
    """
    root = argparse.ArgumentParser(
        description=
        f"""
multi git repositories mng
""")
    root.set_defaults(func=lambda *args: root.print_help())

    sub_cmds = root.add_subparsers(help=f"supported cmds:")
    curr_module = inspect.getmodule(inspect.currentframe())
    for name, obj in inspect.getmembers(curr_module):
        if inspect.isclass(obj) and issubclass(obj, CmdBase) and name != "CmdBase":
            logger.debug(f"get one cmd {name}")
            build_args(sub_cmds, obj)

    args = root.parse_args(args)
    # execute
    args.func(args)


def find_file_in_parent_dir(start_path, file_name: str):
    """
    find file in curr or parent dir, return relative path
    """
    start_path = pathlib.Path(start_path).absolute()
    path = start_path
    assert path.is_dir()
    while True:
        logger.debug(f"find {path} {file_name}")
        f = path / file_name
        if f.exists() and f.is_file():
            result = start_path.relative_to(path)
            logger.debug(f"success find at {path} {result}")
            return result, path
        if path.parent == path:
            logger.debug(f"end find {path}")
            break
        path = path.parent.absolute()
    return None, None


def create_and_run_cmd(cls, *args, **kwargs):
    curr_path = os.getcwd()
    curr_path = os.getcwd()
    curr_path = pathlib.Path(curr_path).absolute()

    # find config file
    relative_path, base_path = find_file_in_parent_dir(curr_path, CONFIG_FILE_NAME)
    assert relative_path is not None

    # load config file
    conf = configparser.ConfigParser()
    assert len(conf.read((base_path / CONFIG_FILE_NAME).absolute())) == 1

    # select needs
    need_exec = []
    for item in conf.sections():
        if item.title() == "__Global__":
            continue
        local_path = (base_path / conf[item]["local"]).absolute()
        if local_path == curr_path or local_path.is_relative_to(curr_path):
            logger.debug(f"add to exec {local_path}")
            need_exec.append(item)
        else:
            logger.debug(f"ignore {local_path}")
    logger.info(f"will exec : {need_exec}")

    # execute
    global_conf = conf["__Global__"]
    for item in need_exec:
        cls(global_conf, conf[item], base_path, item).run(*args, **kwargs)
    pass


class CmdBase:
    cmd = "CmdBase"
    description = "CmdBase desc"
    help = description

    @staticmethod
    def run_cmd(cls, *args, **kwargs):
        return create_and_run_cmd(cls, *args, **kwargs)

    def __init__(self, global_conf, curr_conf, base_path, curr_name):
        self.global_conf = global_conf
        self.curr_conf = curr_conf
        self.base_path: pathlib.Path = base_path
        self.curr_name = curr_name

        self.logger = logging.getLogger(self.log_tag())
        pass

    def log_tag(self):
        return f"{self.__class__.__name__}:{self.curr_name}"

    def value_or_default(self, key: str, default=None) -> str:
        if key in self.curr_conf:
            return self.curr_conf[key]
        if key in self.global_conf:
            return self.global_conf[key]
        return default

    def value(self, key: str) -> str:
        if key in self.curr_conf:
            return self.curr_conf[key]
        if key in self.global_conf:
            return self.global_conf[key]
        raise KeyError(f"key {key} not exists")

    def run(self, *args, **kwargs):
        pass


# ---------- repositories mng  ----------

class TestCmd(CmdBase):
    cmd = "test"
    description = "test cmd args, just print input"
    help = description

    def run(self, arg1: int, arg2, arg3=1, arg4=2, arg5: int = None):
        """
        :param arg1  : arg1 desc str
        :param arg4  : arg4 desc str
        """
        self.logger.debug(f"{arg1} {arg2} {arg3} {arg4} {arg5}")
        pass


class GitCloneCmd(CmdBase):
    cmd = "clone"
    description = "clone repositories in config"
    help = description

    def run(self):
        local_path = self.value("local")
        if (self.base_path / local_path).exists():
            logger.info(f"ignore exists {self.curr_name} {local_path}")
            return
        recursive = self.value_or_default("recursive", "true")
        if recursive.strip(' ').upper() == 'TRUE':
            recursive_str = " --recursive "
        else:
            recursive_str = ""

        remote_path = self.value("remote")

        cmd = f'cd {self.base_path} && git clone {recursive_str} "{remote_path}" "{local_path}" '
        logger.debug(f"will run -- {cmd} --")
        execute_cmd(cmd, self.log_tag())
        pass


def run_cmd_in_repository_dir(cmd_obj, cmd_str):
    local_path = cmd_obj.value("local")
    curr_path = cmd_obj.base_path / local_path
    if not (curr_path).exists():
        logger.info(f"project not cloned, ignore {cmd_obj.curr_name} {local_path}")
        return
    cmd = f'cd "{curr_path}" && {cmd_str}'
    logger.debug(f"will run -- {cmd} --")
    execute_cmd(cmd, cmd_obj.log_tag())


def execute_cmd(cmd: str, log_tag=""):
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        text=True,
        bufsize=1
    )
    log = logging.getLogger(log_tag)
    while process.poll() is None:
        # 从stdout输出读取内容
        stdout_line = process.stdout.readline().strip()
        if stdout_line:
            log.info(f"{stdout_line}")

        # 从stderr输出读取内容
        stderr_line = process.stderr.readline().strip()
        if stderr_line:
            log.error(f"{stderr_line}")

    # 读取任何剩余的输出
    remaining_stdout, remaining_stderr = process.communicate()

    if remaining_stdout.strip():
        log.info(f"{remaining_stdout.strip()}")
    if remaining_stderr.strip():
        log.error(f"{remaining_stderr.strip()}")
    return process.wait()


class GitAnyCmd(CmdBase):
    cmd = "cmd"
    description = "run any cmd in each repository's dir"
    help = description

    def run(self, cmd: str):
        """
        :param cmd : any
        """
        run_cmd_in_repository_dir(self, cmd)
        pass


class GitUpdateCmd(CmdBase):
    cmd = "update"
    description = "update repositories in config"
    help = description

    def run(self, ignore_sub: bool = False):
        """
        :param ignore_sub : ignore update sub module
        """
        recursive_str = " --recurse-submodules"
        if ignore_sub:
            recursive_str = ""
        run_cmd_in_repository_dir(self, f'git pull {recursive_str}')
        pass


class GitUpdateCmd(CmdBase):
    cmd = "checkout"
    description = "recursive update repositories in config"
    help = description

    def run(self, branch: str, r: bool = False):
        """
        :param branch : specified branch
        :param r : recurse submodule
        """
        #  git -c credential.helper= pull --recurse-submodules --progress origin better_game
        cmd = f'git checkout {branch} && git pull '
        if r:
            cmd += f' && git submodule foreach "git checkout {branch} && git pull"'
        run_cmd_in_repository_dir(self, cmd)
        pass


class GitUpdateCmd(CmdBase):
    cmd = "status"
    description = "recursive update repositories in config"
    help = description

    def run(self, r: bool = False):
        """
        :param r : recurse submodule
        """
        #  git -c credential.helper= pull --recurse-submodules --progress origin better_game
        cmd = f'git status'
        if r:
            cmd += f' && git submodule foreach "git status"'
        run_cmd_in_repository_dir(self, cmd)
        pass


if __name__ == '__main__':
    logger.debug("============= start =============")
    cmd_main()
    pass
