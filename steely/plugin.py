from enum import Enum


class CommandPartType(Enum):
    # A subcommand, eg. the token "set" in "/np set <username>".
    SUBCOMMAND = 1
    # A required argument to the command, eg. "<username>" in "/np set
    # <username>". Required arguments are denoted by some token surrounded by
    # <pointy brackets>. In this example, that CommandPart will have the name
    # "username".
    REQUIRED_ARGUMENT = 2
    # An optional argument to the command, eg. the token "[username]" in "/np
    # [username]". Optional arguments are denoted by some token surrounded by
    # [square brackets]. In this example, that CommandPart will have the name
    # "username".
    OPTIONAL_ARGUMENT = 3


class PluginCommand:

    class CommandPart:

        def __init__(self, _str):
            self._str = _str
            # TODO(iandioch): Handle zero-len strings edge case
            if _str[0] == '<' and _str[-1] == '>':
                self.type = CommandPartType.REQUIRED_ARGUMENT
                self.name = _str[1:-1]
            elif _str[0] == '[' and _str[-1] == ']':
                # Optional arg
                self.type = CommandPartType.OPTIONAL_ARGUMENT
                self.name = _str[1:-1]
            else:
                self.type = CommandPartType.SUBCOMMAND
                self.name = _str

    def __init__(self, command, func):
        self.command = command
        self.func = func

        self.command_parts = self._parse_defined_command_parts(command)

    def _parse_defined_command_parts(self, command_str):
        parts = command_str.split(' ')
        return [PluginCommand.CommandPart(part) for part in parts]

    def _parse_command_call(self, expected_command_parts, called_command_parts):
        # Returns the number of matched parts, the string length matched, and a
        # dict of the parsed args.
        parsed_args = {}
        i = 0
        str_match_len = 0
        while i < len(expected_command_parts) and i < len(called_command_parts):
            expected_part = expected_command_parts[i]
            if expected_part.type is CommandPartType.SUBCOMMAND:
                # Required str, must match exactly.
                if called_command_parts[i] == expected_part.name:
                    str_match_len += len(called_command_parts[i])
                    i += 1
                    continue
                else:
                    # Expected some specific str, got something else, abort.
                    return 0, 0, {}

            elif expected_part.type is CommandPartType.REQUIRED_ARGUMENT:
                parsed_args[expected_part.name] = called_command_parts[i]
                str_match_len += len(called_command_parts[i])
                i += 1

            elif expected_part.type is CommandPartType.OPTIONAL_ARGUMENT:
                # If the expected command is "/help [search_str] <topic>" to
                # yield only the part of the helpstring for "topic" relevant to
                # "search_str", and the called command is "/help jamiroquai",
                # then decide if we should count "jamiroquai" as a search_str
                # or as a topic for a better overall match.
                print('Trying to match part "{}" against optional command "{}".'.format(
                    called_command_parts[i], expected_command_parts[i].name))

                i_matched, len_matched, args_matched = self._parse_command_call(
                    expected_command_parts[i + 1:], called_command_parts[i + 1:])
                len_matched += len(called_command_parts[i])
                args_matched[expected_command_parts[
                    i].name] = called_command_parts[i]
                print('If matched: ({}, {}, {})'.format(
                    i_matched, len_matched, args_matched))

                i_not_matched, len_not_matched, args_not_matched = self._parse_command_call(
                    expected_command_parts[i + 1:], called_command_parts[i:])
                print('If not matched: ({}, {}, {})'.format(
                    i_not_matched, len_not_matched, args_not_matched))

                # Choose whether matching or not matching this optional argument
                # creates a better overall match for the string...
                best_match_i = i_not_matched
                best_match_len = len_not_matched
                best_matched_args = args_not_matched
                if i_matched >= i_not_matched:
                    print('Matching "{}" against "{}" is better than not.'.format(
                        called_command_parts[i], expected_command_parts[i].name))
                    best_match_i = i_matched
                    best_match_len = len_matched
                    best_matched_args = args_matched

                print(best_match_i, best_matched_args)

                # We must add + here because the optional arg was matched either
                # way, as it is optional...
                i += best_match_i + 1
                parsed_args.update(best_matched_args)
                str_match_len += best_match_len

        # If we reached the end of the input string and there is still something
        # expected that _must_ be matched, then this avenue is useless, return
        # no match.
        if i < len(expected_command_parts):
            for other_expected_part in expected_command_parts[i:]:
                if other_expected_part.type in [CommandPartType.REQUIRED_ARGUMENT,
                                                CommandPartType.SUBCOMMAND]:
                    print('Reached end of command call str, but no match found for "{}".'.format(
                        other_expected_part.name))
                    return 0, 0, {}

        # We don't want i to ever be greater than len(expected_command_parts)...
        # Not that this should happen.
        i = min(i, len(expected_command_parts))

        print('Matched {} parts for call "{}" in plugin "{}"'.format(
            i, called_command_parts, self.command))
        print('This has matched args: ', parsed_args)
        return i, str_match_len, parsed_args

    def get_best_match(self, called_command_parts):
        # Returns (parts matched, str length of match, matched args dict)
        return self._parse_command_call(self.command_parts, called_command_parts)


class PluginManager:
    _command_listeners = []  # A list of PluginCommands.
    _passive_listeners = []  # A list of plain funcs.

    @classmethod
    def get_passive_listeners(cls):
        return cls._passive_listeners

    @classmethod
    def get_listener_for_command(cls, command):
        # assumes "command" does not start with "/". Eg., for "/np top 7day", "command" would be "np top 7day"
        # returns longest matching command and a func to be called against
        # "command"

        command = command.lower().strip()
        print('Finding longest match for "/{}".'.format(command))
        print('Active listeners:', ', '.join(
            c.command for c in cls._command_listeners))

        command_parts = command.split(' ')

        # TODO(iandioch): Should fix the bug where "/np helperson" would yield
        # "/np help" instead of giving "/np" for user "helperson"
        longest_matching_listener = None
        longest_match = 0

        best_match_num_parts = 0
        best_match_str_len = 0
        best_match_args = {}
        best_match_plugin = None

        for plugin_command in cls._command_listeners:
            num_parts, str_len, args = plugin_command.get_best_match(
                command_parts)
            if (num_parts > best_match_num_parts) or (num_parts == best_match_num_parts and str_len > best_match_str_len):
                best_match_num_parts = num_parts
                best_match_str_len = str_len
                best_match_args = args
                best_match_plugin = plugin_command

        if best_match_plugin is None:
            print('No best matching plugin found for call "{}"'.format(command))
            return None, None, None

        # The + best_match_num_parts - 1 part of this is required to account for
        # the spaces between command parts that are matched but never added
        # anywhere before.
        total_str_match_len = best_match_str_len + best_match_num_parts - 1

        print('Best matching plugin for call "{}" is "{}", with args: {}'.format(
            command, best_match_plugin.command, best_match_args))
        print('This matches {} parts, with prefix substr "{}".'.format(
            best_match_num_parts, command[:total_str_match_len]))
        return command[:total_str_match_len], best_match_plugin.func, best_match_args

    @classmethod
    def add_passive_listener(cls, func):
        cls._passive_listeners.append(func)

    @classmethod
    def add_listener_for_command(cls, command, func):
        cls._command_listeners.append(PluginCommand(command, func))

    @staticmethod
    def load_plugins():
        import plugins.letterboxd.main


class Plugin:

    def __init__(self, name, author, help):
        self.name = name
        self.author = author
        self.help = help
        # .active decides whether the plugin is available to be used.
        self.active = True
        self.commands = []

    def setup(self):
        # TODO(iandioch): Right now, this decorator must be run like the following:
        # @setup()
        # def setup_func():
        #   ...
        #
        # However, it should also be possible to run it without the brackets after @setup,
        # as a naked decorator.
        def wrapper(func):
            try:
                result = func()
                if result is not None:
                    print('Received error while running setup for plugin "{}":\n{}.'.format(
                        self.name, result))
                    print(self.name)
                    self.active = False
            except Exception as e:
                print('Error thrown while running setup for plugin "{}":\n{}.'.format(
                    self.name, e))
                self.active = False
            return func

        print('active?', self.active)
        # TODO(iandioch): Add the helpstring so that '/help name' might work.
        # TODO(iandioch): Consider the fact that "name" and the specific listed commands might be different.
        # TODO(iandioch): Consider that someone shouldn't have to repeat the
        # same root command for all different @plugin.listen() methods in that
        # plugin.
        return wrapper

    def listen(self, command=None):
        # TODO(iandioch): Make it possible to run this as a naked decorator for
        # plugins that are passively listening.
        if not self.active:
            print('Tried to set up listener "{}" for plugin "{}", but plugin is not active.'.format(
                command, self.name))
            # Return a do-nothing decorator, as we don't want to register this
            # command.
            return lambda _: None

        print('Adding command "{}" to plugin "{}" by "{}".'.format(
            command, self.name, self.author))
        # TODO(iandioch): Add functools.wraps() to update __name__, etc.

        def register_listener(func):
            if command is None:
                PluginManager.add_passive_listener(func)
            else:
                PluginManager.add_listener_for_command(command, func)

            return func

        if command is not None:
            print('Adding command {} to list for plugin {}'.format(
                command, self.name))
            self.commands.append(command)

        return register_listener


def create_plugin(name=None, author=None, help=None):
    return Plugin(name, author, help)

if __name__ == '__main__':
    PluginManager.load_plugins()
