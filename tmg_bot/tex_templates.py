DEFAULT_TEX_TEMPLATE: str = """
\\documentclass[preview]{{standalone}}
\\usepackage[spanish]{{babel}}
\\usepackage{{amsmath}}
\\usepackage{{amssymb}}
\\usepackage{{xcolor}}
\\usepackage{{mlmodern}}
\\usepackage{{hyperref}}
\\usepackage{{minted}}
\\def\\markdownOptionOutputDir{{temp}}
\\usepackage[smartEllipses,hashEnumerators,fencedCode]{{markdown}}
\\markdownSetup{{renderers={{
  link = {{\href{{#2}}{{#1}}}}
}}}}
\\usemintedstyle{{github-dark}}
\\begin{{document}}
\\color{{white}}
\\begin{{markdown}}[texMathDollars,texMathSingleBackslash,texMathDoubleBackslash]
{md}
\\end{{markdown}}
\\end{{document}}
""".strip()
