DEFAULT_TEX_TEMPLATE: str = """
\\documentclass[preview]{{standalone}}
\\usepackage[spanish]{{babel}}
\\usepackage{{amsmath}}
\\usepackage{{amssymb}}
\\usepackage{{xcolor}}
\\usepackage{{mlmodern}}
\\usepackage{{hyperref}}
\\usepackage[outputdir=temp]{{minted}}
\\usepackage[smartEllipses,hashEnumerators,fencedCode]{{markdown}}
\\markdownSetup{{renderers={{
  link = {{\href{{#2}}{{#1}}}}
}}, outputDir=temp}}
\\usemintedstyle{{nord}}
\\begin{{document}}
\\color{{white}}
\\begin{{markdown}}[texMathDollars,texMathSingleBackslash,texMathDoubleBackslash]
{md}
\\end{{markdown}}
\\end{{document}}
""".strip()
