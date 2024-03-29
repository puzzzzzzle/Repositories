#!/usr/bin/env python3
# author : puzzzzzzle
# email : 2359173906@qq.com
# desc : mng multi git repositories, only depends on python 3.5+

import concurrent.futures
import configparser
import argparse
import inspect
import logging
import functools
import multiprocessing
import os
import pathlib
import re
import subprocess
import time


# ---------- logger ----------


def create_cli_log(tag: str, format_str: str):
    # create logger
    tmp_log = logging.getLogger(tag)
    # create cli handle
    logger_handle = logging.StreamHandler()
    logger_handle.setLevel(LOG_LEVEL)
    # set formatter
    formatter = logging.Formatter(format_str)
    logger_handle.setFormatter(formatter)
    # add handle
    tmp_log.addHandler(logger_handle)
    return tmp_log


LOG_LEVEL = logging.INFO
logging.basicConfig(level=LOG_LEVEL)
logging.getLogger().handlers.clear()
cmd_logger = create_cli_log("cmd", '%(message)s')
# logger = create_cli_log("main", '|%(asctime)s|%(name)s|%(levelname)s|%(message)s')
logger = cmd_logger


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


def build_args(sub_cmds, cls, run_func_name="run"):
    """
    build args for parser by function define
    """

    class MyHelpFormatter(argparse.ArgumentDefaultsHelpFormatter):
        def _format_args(self, action, default_metavar):
            return action.metavar

    parser = sub_cmds.add_parser(cls.cmd, description=cls.description,
                                 help=cls.help, formatter_class=MyHelpFormatter)

    run_func = getattr(cls, run_func_name)
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
            help_str = f"{get_param_description(run_func, arg)}"
            if t == bool:
                del paras["type"]
                if value:
                    help_str += f", default is set, add flags to set false"
                    paras["action"] = "store_false"
                else:
                    help_str += f", default is not set, add flags to set true"
                    paras["action"] = "store_true"

                paras["help"] = help_str
            else:
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


def execute_cmd(cmd: str, force_log=False):
    start_time = time.time()

    def long_time_log(log_func, msg):
        if force_log or time.time() - start_time > 3:
            log_func(msg)

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        text=True,
        bufsize=1
    )
    stdout_lines = []
    stderr_lines = []
    while process.poll() is None:
        # 从stdout输出读取内容
        stdout_line = process.stdout.readline()
        if stdout_line is not None:
            long_time_log(cmd_logger.info, stdout_line)
            stdout_lines.append(stdout_line)
        # 从stderr输出读取内容
        stderr_line = process.stderr.readline()
        if stderr_line:
            long_time_log(cmd_logger.error, stdout_line)
            stderr_lines.append(stdout_line)

    # 读取任何剩余的输出
    remaining_stdout, remaining_stderr = process.communicate()

    if remaining_stdout.strip():
        long_time_log(cmd_logger.info, remaining_stderr)
        stdout_lines.append(remaining_stderr)
    if remaining_stderr.strip():
        long_time_log(cmd_logger.error, remaining_stderr)
        stderr_lines.append(remaining_stderr)
    return process.wait(), stdout_lines, stderr_lines, cmd


def execute_cmd_in_rep_dir(cmd_obj, cmd_str, force_log=False):
    local_path = cmd_obj.value("local")
    curr_path = cmd_obj.base_path / local_path
    if not curr_path.exists():
        logger.info(f"project not cloned, ignore {cmd_obj.curr_name} {local_path}")
        return 0, [], [], cmd_str
    cmd = f'cd "{curr_path}" && {cmd_str}'
    logger.debug(f"will run -- {cmd} --")
    return execute_cmd(cmd, force_log)


def cmd_execute_worker(item, cls, conf, base_path, *args, **kwargs):
    global_conf = conf["__Global__"]
    cmd = cls(global_conf, conf[item], base_path, item)
    ret, info, err, cmd = cmd.run(*args, **kwargs)
    success = ret == 0
    header = "\n>>>>>>>>>>"
    if success:
        header += f"run success at {item}:"
    else:
        header += f"run fail at {item}:"
    body = ""
    if True or not success:
        body += f'\ncmd:{cmd}\n'
        for line in info:
            body += line
    if len(err) > 0:
        body += "err info:\n"
        for line in err:
            body += line
    body += "<<<<<<<<<<\n"

    if success:
        cmd_logger.debug(header + body)
    else:
        cmd_logger.error(header + body)
    return success, item


def create_and_run_cmd(cls, *args, **kwargs):
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

    # execute
    global_conf = conf["__Global__"]

    # for item in need_exec:
    #     run_item(item)
    jobs = cls.jobs_num
    if "jobs" in global_conf:
        jobs = int(global_conf["jobs"])
    cmd_logger.info(f"run with jobs {jobs}")
    assert jobs > 0
    curr_pool = concurrent.futures.ThreadPoolExecutor
    # curr_pool = concurrent.futures.ProcessPoolExecutor
    with curr_pool(max_workers=jobs) as executor:
        tasks = []
        for item in need_exec:
            fu = executor.submit(cmd_execute_worker, item, cls, conf, base_path, *args, **kwargs)
            tasks.append(fu)
        success_tasks = []
        fail_tasks = []
        for fu in concurrent.futures.as_completed(tasks):
            success, item = fu.result()
            if success:
                success_tasks.append(item)
            else:
                fail_tasks.append(item)
        info = f"total:{len(need_exec)} success:{len(success_tasks)} fail:{len(fail_tasks)}:{fail_tasks}"
        if len(fail_tasks) > 0:
            info += f" fail tasks:{fail_tasks}"
        cmd_logger.info(info)


class CmdBase:
    cmd = "CmdBase"
    description = "CmdBase desc"
    help = description
    jobs_num = multiprocessing.cpu_count()

    @staticmethod
    def run_cmd(cls, *args, **kwargs):
        return create_and_run_cmd(cls, *args, **kwargs)

    def __init__(self, global_conf, curr_conf, base_path, curr_name):
        self.global_conf = global_conf
        self.curr_conf = curr_conf
        self.base_path: pathlib.Path = base_path
        self.curr_name = curr_name
        pass

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
        return 0, [], [], ""


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
        cmd_logger.info(f"{arg1} {arg2} {arg3} {arg4} {arg5}")
        return 0, [], [], ""
        pass


class GitCloneCmd(CmdBase):
    cmd = "clone"
    description = "clone repositories in config"
    help = description

    def run(self):
        local_path = self.value("local")
        if (self.base_path / local_path).exists():
            cmd_logger.debug(f"ignore exists {self.curr_name} {local_path}")
            return 0, [], [], "ignore exists"
        recursive = self.value_or_default("recursive", "true")
        if recursive.strip(' ').upper() == 'TRUE':
            recursive_str = " --recursive "
        else:
            recursive_str = ""

        remote_path = self.value("remote")

        cmd = f'cd {self.base_path} && git clone {recursive_str} "{remote_path}" "{local_path}" '
        return execute_cmd(cmd)


class GitAnyCmd(CmdBase):
    cmd = "cmd"
    description = "run any cmd in each repository's dir"
    help = description

    def run(self, cmd: str):
        """
        :param cmd : any
        """
        return execute_cmd_in_rep_dir(self, cmd)
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
        return execute_cmd_in_rep_dir(self, f'git pull {recursive_str}')
        pass


class GitCheckoutCmd(CmdBase):
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
        return execute_cmd_in_rep_dir(self, cmd)
        pass


class GitStatusCmd(CmdBase):
    cmd = "status"
    description = "recursive update repositories in config"
    help = description
    jobs_num = 1

    def run(self, r: bool = False):
        """
        :param r : recurse submodule
        """
        #  git -c credential.helper= pull --recurse-submodules --progress origin better_game
        cmd = f'git status'
        if r:
            cmd += f' && git submodule foreach "git status"'
        cmd_logger.info(f"----------- git status at {self.curr_name} -----------")
        ret = execute_cmd_in_rep_dir(self, cmd, True)
        # cmd_logger.info(f"----------- git status end {self.curr_name} -----------\n")
        return ret


class GitConfUserCmd(CmdBase):
    cmd = "user"
    description = "set user's name and email"
    help = description

    def run(self, user_name: str, email: str, r: bool = False):
        """
        :param user_name : git user's name
        :param email : git user's email
        :param r : recurse submodule
        """
        set_one = f'git config user.name {user_name} && git config user.email {email}'
        cmd = set_one
        if r:
            cmd += f' && git submodule foreach "{set_one}"'
        cmd_logger.info(f"run at {self.curr_name} : {cmd}")
        ret = execute_cmd_in_rep_dir(self, cmd, True)
        return ret


if __name__ == '__main__':
    cmd_main()
    pass
