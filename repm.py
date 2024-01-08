#!/usr/bin/env python3
# author : puzzzzzzle
# email : 2359173906@qq.com
# desc : mng multi git repositories, only depends on python 3.5+

import concurrent.futures
import configparser
import argparse
import copy
import inspect
import logging
import functools
import multiprocessing
import os
import pathlib
import re

import yaml
from git import repo


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


# ---------- repositories mng base define ----------
class GitCmdRunner:
    CONFIG_FILE_NAME = "Repositories.yaml"

    def __init__(self):
        curr_path = os.getcwd()
        curr_path = pathlib.Path(curr_path).absolute()
        # find config file
        relative_path, base_path = find_file_in_parent_dir(curr_path, GitCmdRunner.CONFIG_FILE_NAME)
        assert relative_path is not None
        self.relative_path = relative_path
        self.base_path = base_path
        self.current_path = curr_path

    def create_and_run_cmd(self, cls, *args, **kwargs):
        base_path = self.base_path
        # load config file
        with open((base_path / self.CONFIG_FILE_NAME)) as f:
            conf: dict = yaml.load(f, yaml.FullLoader)

        global_conf = conf["global_config"] or {}
        jobs = global_conf.get("jobs", cls.jobs_num)
        assert jobs > 0
        cmd_logger.info(f"run with jobs {jobs}")
        all_repos = conf["all_repos"] or {}

        # select needs
        need_exec = []
        for category_name, category_repos in all_repos.items():
            if category_name == "__root__":
                sub_path = ""
            else:
                sub_path = "category_name/"
            logger.debug(f"{category_name}")
            for repo_name, repo_conf in category_repos.items():
                repo_conf = copy.deepcopy(repo_conf)
                local_dir = sub_path + (repo_conf["local"] or repo_name)
                repo_conf["local"] = local_dir
                repo_conf["name"] = repo_name
                need_exec.append(repo_conf)
                pass

        curr_pool = concurrent.futures.ThreadPoolExecutor
        with curr_pool(max_workers=jobs) as executor:
            tasks = []
            for item in need_exec:
                fu = executor.submit(GitCmdRunner.cmd_execute_worker, item, cls, global_conf, base_path, *args,
                                     **kwargs)
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

    @staticmethod
    def cmd_execute_worker(item, cls, global_conf, base_path, *args, **kwargs):
        cmd = cls(global_conf, item, base_path)
        ret, info, err = cmd.run(*args, **kwargs)
        success = (ret == 0)
        return success, item


runner = GitCmdRunner()


class CmdBase:
    cmd = "CmdBase"
    description = "CmdBase desc"
    help = description
    jobs_num = multiprocessing.cpu_count()

    @staticmethod
    def run_cmd(cls, *args, **kwargs):
        return runner.create_and_run_cmd(cls, *args, **kwargs)

    def __init__(self, global_conf, curr_conf, base_path):
        self.global_conf = global_conf
        self.curr_conf = curr_conf
        self.base_path: pathlib.Path = base_path
        self.curr_repo = None
        pass

    @property
    def name(self):
        return self.curr_conf["name"]

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

    @property
    def repository(self):
        if self.curr_repo is not None:
            return self.curr_repo
        local_path = self.value("local")
        curr_path = self.base_path / local_path
        if not curr_path.exists():
            logger.info(f"project not cloned, ignore {self.name} {local_path}")
            return None

        self.curr_repo = repo.Repo(self.value("local"))
        return self.curr_repo

    def execute_cmd_in_rep_dir(self, cmd_str):
        if self.repository is None:
            return 0, "", f"project not cloned, ignore {self.name}"
        status, stdout, stderr = self.repository.git.execute(cmd_str, with_extended_output=True)
        return status, stdout, stderr

    def run(self, *args, **kwargs):
        return 0, "", ""


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
        return 0, "", ""
        pass


class GitCloneCmd(CmdBase):
    cmd = "clone"
    description = "clone repositories in config"
    help = description

    def run(self):
        local_path = self.value("local")
        if (self.base_path / local_path).exists():
            cmd_logger.debug(f"ignore exists {self.name} {local_path}")
            return 0, "", "ignore exists"
        recursive = self.value_or_default("recursive", True)
        remote_path = self.value("remote")
        cmd_logger.info(f"will clone {remote_path} to {local_path}")
        try:
            repo.Repo.clone_from(remote_path, local_path, recursive=recursive)
            cmd_logger.info(f"done {local_path}")
            return 0, "", ""
        except Exception as e:
            cmd_logger.error(f"fail {local_path}")
            return -1, "", f"clone fail {local_path} {remote_path} {e}"


class GitAnyCmd(CmdBase):
    cmd = "cmd"
    description = "run any cmd in each repository's dir"
    help = description

    def run(self, cmd: str):
        """
        :param cmd : any
        """
        cmd_logger.info(f"running {cmd} as {self.name}")
        return self.execute_cmd_in_rep_dir(cmd)


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
        return self.execute_cmd_in_rep_dir(f'git pull {recursive_str}')


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
        return self.execute_cmd_in_rep_dir(cmd)


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
        status, stdout, stderr = self.execute_cmd_in_rep_dir(cmd)
        assert status == 0
        logger.info(f"status at {self.name}\n{stdout}\n{stderr}")
        return status, stdout, stderr


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
        cmd_logger.info(f"run at {self.name} : {cmd}")
        ret = self.execute_cmd_in_rep_dir(cmd)
        return ret


if __name__ == '__main__':
    cmd_main()
    pass
