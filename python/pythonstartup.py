def pythonstartup():
    import sys
    from os.path import expanduser
    import rlcompleter
    import tokenize
    from functools import wraps
    
    try:  # Python 3
        import builtins
    except ImportError:  # Python < 3
        import __builtin__ as builtins
    
    HISTFILE = expanduser("~/.python_history")
    def history_read():
        try:
            readline.read_history_file(HISTFILE)
        except EnvironmentError:
            pass
    def history_write():
        readline.write_history_file(HISTFILE)
    
    def excepthook(func):
        @wraps(func)
        def wrapper(*pos, **kw):
            try:
                return func(*pos, **kw)
            except:
                sys.excepthook(*sys.exc_info())
                raise
        return wrapper
    
    class Completer(rlcompleter.Completer):
        def _callable_postfix(self, val, word):
            if readline.get_completion_type() == ord("\t"):
                return word
            else:
                return rlcompleter.Completer._callable_postfix(
                    self, val, word)
        
        def global_matches(self, text):
            return self.get_matches(text,
                rlcompleter.Completer.global_matches)
        def attr_matches(self, text):
            return self.get_matches(text, rlcompleter.Completer.attr_matches)
        @excepthook
        def get_matches(self, text, default):
            # Chop off any unfinished token at the cursor
            line = readline.get_line_buffer()
            i = readline.get_endidx()
            
            # Just insert tab characters at the beginning of lines
            linestart = line.rfind("\n", 0, i) + 1  # 0 if no newline
            if linestart == i or line[linestart:i].isspace():
                return (text + "\t",)
            
            while i > 0:
                c = line[i - 1]
                if not c.isalnum() and c != "_" and ord(c) < 128:
                    break
                i -= 1
            prefix = line[readline.get_begidx():i]
            
            gen = self.tokenize(line[:i])
            func = None  # Current function name in expression
            constructor = None  # Constructor name just called
            attrcon = None  # Constructor name in attribute access
            
            # Stack of function names being called for each bracket, or None
            # for other bracket instances
            bracket_funcs = list()
            
            stmt = True  # Ready to start a new statement?
            while True:
                (type, string) = self.skip_linecont(gen)
                if type == tokenize.ENDMARKER:
                    break
                if stmt and string in ("import", "from"):
                    packages = list()
                    while True:
                        (type, string) = self.skip_linecont(gen)
                        if type == tokenize.ENDMARKER:
                            matches = list()
                            for match in self.import_list(packages, prefix):
                                if match.startswith(text):
                                    matches.append(match)
                            return matches
                        if type != tokenize.NAME:
                            break
                        packages.append(string)
                        (_, string) = self.skip_linecont(gen)
                        if string != ".":
                            break
                    
                    if string == "import":
                        while True:
                            (type, string) = self.skip_linecont(gen)
                            if type == tokenize.ENDMARKER:
                                matches = list()
                                for match in self.from_list(packages):
                                    if match.startswith(text):
                                        matches.append(match)
                                return matches
                            if type == tokenize.NAME:
                                while True:
                                    (type, string) = self.skip_linecont(gen)
                                    if string != ")":
                                        break
                                if string != ",":
                                    break
                            elif string != "(":
                                break
                
                if string == "(":
                    bracket_funcs.append(func)
                if string in set("[{"):
                    bracket_funcs.append(None)
                
                if string == ".":
                    attrcon = constructor
                else:
                    attrcon = None
                
                if string in set(")]}") and bracket_funcs:
                    constructor = bracket_funcs.pop()
                else:
                    constructor = None
                
                if type == tokenize.NAME:
                    func = string
                else:
                    func = None
                
                # Could next token be a function parameter?
                param = string in set("(,")
                
                stmt = not bracket_funcs and (
                    type == tokenize.NEWLINE or string in set(":;"))
            
            matches = default(self, text)
            self.edit_keywords(matches)
            
            if bracket_funcs:
                func = bracket_funcs[-1]
                if func and param:
                    if func in self.namespace:
                        func = self.namespace[func]
                    else:
                        func = getattr(builtins, func, None)
                    for arg in self.arg_list(func):
                        if arg.startswith(text):
                            matches.append(arg + "=")
            if attrcon:
                if attrcon in self.namespace:
                    attrs = dir(self.namespace[attrcon])
                elif hasattr(builtins, attrcon):
                    attrs = dir(getattr(builtins, attrcon))
                else:
                    attrs = ()
                for attr in attrs:
                    attr = prefix + attr
                    if attr.startswith(text):
                        matches.append(attr)
            
            return matches
        
        def skip_linecont(self, gen):
            """Get the next token, but skip non-terminating newlines"""
            while True:
                (type, string) = self.skip_comment(gen)
                if type != tokenize.NL:
                    return (type, string)
        
        def skip_comment(self, gen):
            """Get the next token, but skip comments before the end marker"""
            (type, string) = next(gen)
            while type == tokenize.COMMENT:
                (type, string) = next(gen)
                if type == tokenize.ENDMARKER:
                    return (tokenize.COMMENT, str())
            return (type, string)
        
        def tokenize(self, code):
            # Want Python 3's tokenize(), or generate_tokens() from before
            # Python 3. Functions of both names may exist in both versions,
            # which makes it hard to detect the appropriate version.
            ENCODING = getattr(tokenize, "ENCODING", None)
            if ENCODING is not None:  # Python 3
                from io import BytesIO
                gen = tokenize.tokenize(BytesIO(code.encode()).readline)
            else:  # Python < 3
                from cStringIO import StringIO
                gen = tokenize.generate_tokens(StringIO(code).readline)
            
            while True:
                try:
                    token = next(gen, (tokenize.ENDMARKER, str()))
                except Exception:
                    continue
                (type, string) = token[:2]
                if (type not in
                (ENCODING, tokenize.INDENT, tokenize.DEDENT) and
                # Skip trailing whitespace at EOF error (Python Issue 16152)
                (type != tokenize.ERRORTOKEN or not string.isspace())):
                    yield (type, string)
        
        def edit_keywords(self, matches):
            if readline.get_completion_type() == ord("?"):
                return
            
            # Add a space to keywords when good style says they would always
            # have a space
            from keyword import kwlist
            spaced = set((
                "and", "as", "assert", "class", "def", "del", "elif", "exec",
                "for", "from", "global", "if", "import", "in", "is",
                "nonlocal", "not", "or", "while", "with",
            )).intersection(kwlist)
            for (i, match) in enumerate(matches):
                if match in spaced:
                    matches[i] += " "
        
        def import_list(self, packages, prefix):
            import pkgutil
            
            if not packages:
                for name in IterableBuiltinImporter.iter_modules(prefix):
                    yield name
            
            # Confirm each element is a package before importing it
            name = ""
            for package in packages:
                name += package
                module = sys.modules.get(name)
                if module:
                    if not hasattr(module, "__path__"):  # Not a package
                        return
                else:
                    loader = pkgutil.find_loader(name)
                    if not loader:
                        return
                    is_package = getattr(loader, "is_package", None)
                    if not is_package or not is_package(name):
                        return
                name += "."
            
            if not packages:
                path = None
                
                if "" in sys.path:
                    # Workaround for "pkgutil" skipping over empty paths,
                    # instead of recognising them as the current directory
                    path = list(sys.path)
                    for (i, entry) in enumerate(path):
                        if not entry:
                            path[i] = "."
            
            else:
                if not module:
                    package = name[:-1]  # Avoid trailing dot
                    module = loader.load_module(package)
                path = module.__path__
            
            indicator = readline.get_completion_type() != ord("\t")
            for (_, name, ispkg) in pkgutil.iter_modules(path, prefix):
                if indicator and ispkg:
                    name += "."
                yield name
        
        def from_list(self, path):
            try:
                module = import_module(".".join(path))
            except Exception:
                return
            for name in dir(module):
                yield name
            path = getattr(module, "__path__", None)
            if path:
                import pkgutil
                for (_, name, _) in pkgutil.iter_modules(path):
                    yield name
        
        def arg_list(self, func):
            try:  # Python 3.3
                from inspect import signature, Parameter
            
            except ImportError:
                try:  # Python 3, < 3.3
                    from inspect import getfullargspec as getargspec
                except ImportError:  # Python < 3
                    from inspect import getargspec
                try:
                    argspec = getargspec(func)
                except TypeError:
                    return ()
                return argspec.args + getattr(argspec, "kwonlyargs", list())
            
            else:
                try:
                    params = signature(func).parameters.values()
                except (TypeError, ValueError):
                    return ()
                keywords = {
                    Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY}
                return (param.name for
                    param in params if param.kind in keywords)
    
    try:  # Python 3
        from importlib.machinery import BuiltinImporter
    except ImportError:  # Python < 3
        BuiltinImporter = object
    class IterableBuiltinImporter(BuiltinImporter):
        @classmethod
        def iter_modules(self, prefix=""):
            for name in sys.builtin_module_names:
                yield prefix + name
    
    def import_module(name):
        import importlib
        
        try:
            return importlib.import_module(name)
        finally:
            # Workaround for pre-3.3 Python's "importlib" adding its own
            # implicit finder implementation (not from "sys.path_hooks") to
            # the cache. This breaks pkgutil.iter_modules(), which expects
            # the implicit finder to be represented by None.
            try:  # Python < 3.3
                from importlib._bootstrap import _FileFinder
            except ImportError:
                pass
            else:
                for (key, finder) in tuple(sys.path_importer_cache.items()):
                    if isinstance(finder, _FileFinder):
                        del sys.path_importer_cache[key]
    
    # Monkey-patch SystemExit() so that it does not exit the interpreter
    class SystemExit(BaseException):
        def __init__(self, code=None):
            self.code = code
            BaseException.__init__(self, code)
    builtins.SystemExit = SystemExit
    
    def exit(code=None):
        global SystemExit
        raise SystemExit(code)
    sys.exit = exit
    
    try:
        import readline
    except ImportError:
        pass  # readline not normally available on Windows
    else:
        if __name__ == "__main__":
            globals().update(
                history_read=history_read, history_write=history_write)
            history_read()
            import atexit
            atexit.register(history_write)
            readline.set_completer(Completer().complete)
            readline.parse_and_bind("tab: complete")
    
    if __name__ != "__main__":
        globals().update(locals())
pythonstartup()
del pythonstartup
