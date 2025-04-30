import re

tex_message = re.compile(r"(\$.*?\$)|(\$\$.*?\$\$)|\\\(.*?\\\)|\\\[.*?\\\]", re.DOTALL)
mentions = re.compile(r"<@!?\d+>")
double_quotes = re.compile(r"\"(.*?)\"")
single_quotes = re.compile(r"'(.*?)'")
markdown_list = re.compile(r"^(\*|\+|\-)\s+(.*)", re.MULTILINE)