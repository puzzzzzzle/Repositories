import configparser
import argparse
import inspect
import logging
import functools
import re

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)


def load_config(file: str):
    conf = configparser.ConfigParser()
    conf.read(file, "utf-8")
    return conf


def cmd_main(args=None):
    """
    :return:
    """
    root = argparse.ArgumentParser(description=
                                   f"""
                                    multi git repositories mng
                                   """)
    root.set_defaults(func=lambda *args: root.print_help())

    sub_cmds = root.add_subparsers(help=f"supported cmds:")
    curr_module = inspect.getmodule(inspect.currentframe())
    for name, obj in inspect.getmembers(curr_module):
        if inspect.isclass(obj) and issubclass(obj, CmdBase) and name != "CmdBase":
            logger.debug(f"get one cmd {name}")
            obj.build_args(sub_cmds, obj)
    args = root.parse_args(args)
    # 设置上下文args
    args.func(args)


def get_param_description(function, param_name):
    """
    获取函数中某个参数的注释
    """
    docstring = function.__doc__
    if not docstring:
        return param_name

    # 构建用于从文档字符串中提取参数描述的正则表达式
    pattern = rf":{param_name}\s*:\s*(.+)\s*"
    regex = re.compile(pattern, re.MULTILINE)
    match = regex.search(docstring)

    if match:
        param_desc = match.groups()
        return f"{param_name}:{param_desc[0]}"
    else:
        return param_name


class CmdBase:
    @staticmethod
    def init_io(parser, cls):
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
        # add normal requires args
        cls.normal_args = normal_args
        cls.default_args = default_args
        cls.annotations = annotations
        if len(normal_args) > 0:
            normal_args_help = ""
            for arg in normal_args:
                normal_args_help += f"({get_param_description(run_func, arg)}) "
            parser.add_argument("args", metavar=f'required args({len(normal_args)}):', type=str, nargs=len(normal_args),
                                help=normal_args_help)
        # add default args
        if len(default_args) > 0:
            for arg, value in default_args.items():
                help_str = f"{get_param_description(run_func, arg)}, default={default_args[arg]}"
                if arg in annotations:
                    t = annotations[arg]
                elif value is not None:
                    t = type(value)
                else:
                    t = str

                parser.add_argument(f"--{arg}", type=t, default=value,
                                    help=help_str)

    @staticmethod
    def build_args(sub_cmds, cls):
        parser = sub_cmds.add_parser(cls.cmd, description=cls.description,
                                     help=cls.help)
        cls.init_io(parser, cls)
        parser.set_defaults(func=functools.partial(cls.run_cmd, cls))
        pass

    @staticmethod
    def run_cmd(cls, para):
        normal_args = cls.normal_args
        default_args = cls.default_args
        annotations = cls.annotations
        cmd = cls()
        logger.debug(f"run {cls.__name__} {para}")
        # normal args
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
        # default args
        dargs = dict(default_args)
        for key in default_args.keys():
            attr = getattr(para, key)
            logger.debug(f"get {key} {attr}")
            dargs[key] = attr
        logger.debug(f"default args {dargs}")

        cmd.run(*args, **dargs)
        pass

    def run(self, *args, **kwargs):
        pass

    pass


class TestCmd(CmdBase):
    cmd = "test"
    description = "test cmd args"
    help = ""

    def run(self, arg1: int, arg2, arg3=1, arg4=2, arg5: int = None):
        """
        :arg1  : arg1 desc str
        :arg4  : arg4 desc str
        """
        logger.debug(f"{arg1} {arg2} {arg3} {arg4} {arg5}")
        pass


class GitCloneCmd(CmdBase):
    cmd = "clone"
    description = "clone all repositories in config"
    help = "clone all repositories in config"

    def run(self):
        pass


if __name__ == '__main__':
    logger.debug("start")
    load_config("./Repositories.ini")
    cmd_main()
    pass
