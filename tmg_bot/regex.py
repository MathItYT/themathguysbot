import re

tex_message = re.compile(r"(\$.*?\$)|(\$\$.*?\$\$)|\\\(.*?\\\)|\\\[.*?\\\]")
mentions = re.compile(r"<@!?\d+>")
double_quotes = re.compile(r"\"(.*?)\"")
single_quotes = re.compile(r"'(.*?)'")