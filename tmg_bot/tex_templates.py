DEFAULT_TEX_TEMPLATE: str = """
\\documentclass[preview]{{standalone}}
\\usepackage[spanish]{{babel}}
\\usepackage{{amsmath}}
\\usepackage{{amssymb}}
\\usepackage{{xcolor}}
\\usepackage{{mlmodern}}
\\usepackage{{hyperref}}
\\usepackage{{minted}}
\\usepackage[smartEllipses,hashEnumerators,fencedCode,hybrid]{{markdown}}
\\markdownSetup{{renderers={{
  link = {{\\href{{#2}}{{#1}}}}
}}}}
\\usemintedstyle{{nord}}
\\begin{{document}}
\\color{{white}}
\\begin{{markdown}}
{md}
\\end{{markdown}}
\\end{{document}}
""".strip()
