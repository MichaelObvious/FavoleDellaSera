from enum import Enum
import json
import os
import re
import subprocess
from sys import argv, stdout, stderr, exit

########## TOOLBOX ##########

def print(stream, content):
    stream.write(str(content))

def println(stream, content):
    print(stream, f'{content}\n')

def slurp_file(filepath: str):
    content = ""
    with open(filepath) as f:
        content = f.read()
    return content

def panic(msg):
    println(stderr, msg)
    exit(-1)

########## CONSTANTS ##########

TEMPLATE_FILE = 'template.tex'
FABULAE_DIR = './fabulae'
DROP_CAP_SIZE = 3
BUILD_COMMAND = 'xelatex -interaction=nonstopmode %s'
CONTRIB_FILE = 'contribuerunt.json'

########## TYPES ##########

class MarkdownType(Enum):
    TITLE  = 0
    PAR    = 1
    CENTER = 2
    IMAGE  = 3

class MarkdownElement:
    def __init__(self, type, value):
        self.type = type
        self.value = value

class Document:
    def __init__(self, title: str = '', subtitle: str = '', author: str = '', toc: bool = False, contents: str = '', img_folders: list = None, out_file: str = ''):
        self.title = title
        self.author = author
        self.subtitle = subtitle
        self.toc = toc
        self.contents = contents
        if img_folders == None:
            self.img_folders = []
        else:
            self.img_folders = img_folders
        self.out_file = out_file

########## PROCEDURES ##########

def md_formatting(x:str) -> str:
    y = re.sub(r'\*(?!\s*\*)([^*\n]+)\*', '\\\\textit{ \\1 }', x)
    return y

def parse_md_source(md_source: str) -> list:
    parsed = [] 
    lines = md_source.splitlines(False)

    i = 0
    while i < len(lines):
        line = lines[i]

        if line.startswith('# '):
            title = line.replace('# ', '')
            parsed.append(MarkdownElement(MarkdownType.TITLE, title))
        elif line.startswith('>'):
            center = ''
            while line.startswith('>') and i < len(lines):
                line = lines[i]
                center += line.replace('>', '')
                center += '\n'
                i += 1
            
            parsed.append(MarkdownElement(MarkdownType.CENTER, center))
            continue
        elif line.startswith('!['):
            path = re.sub(r'!\[(.*?)\]\((.*?)\)', '\\2', line)
            caption = re.sub(r'!\[(.*?)\]\((.*?)\)', '\\1', line)
            parsed.append(MarkdownElement(MarkdownType.IMAGE, {'path': path, 'caption': caption}))
        else:
            words = line.replace('\t', ' ').split(' ')
            words = list(filter(lambda x: len(x) > 0, words))
            if len(words) > 0:
                parsed.append(MarkdownElement(MarkdownType.PAR, line))

        i += 1

    return parsed

def md_to_tex_source(parsed: list) -> str:
    content = ''
    placed_drop_cap = False
    center_count = 0

    for mde in parsed:
        if mde.type == MarkdownType.TITLE:
            content += f'\\section{{{mde.value}}}\n'
        elif mde.type == MarkdownType.CENTER:
            if center_count == 0:
                content += f"\\begin{{center}}\n{mde.value}\n\\end{{center}}\n\n\n"
            else:
                if content.endswith('\\\\'):
                    content = content[:-2]
                value = mde.value.replace('\n \n', '\\\\\n')
                content += f"\\begin{{poetry}}\n{value}\n\\end{{poetry}}\n\n\n"
            center_count += 1
        elif mde.type == MarkdownType.PAR:
            if not placed_drop_cap:
                words = mde.value.replace('\t', ' ').split(' ')
                words = list(filter(lambda x: len(x) > 0, words))
                if len(words) > 0:
                    dropcap = words[0][0]
                    dropword = words[0][1:]
                    content += f'\\lettrine[lines={int(DROP_CAP_SIZE)}, findent=3pt, nindent=0pt]{{{dropcap}}}{{{dropword}}} ' + (' '.join(words[1:]) + '\\\\')
                    placed_drop_cap = True
            else:
                content += f'\\indent {mde.value}\\\\'
        elif mde.type == MarkdownType.IMAGE:
            path = mde.value["path"]
            content += f'\\noindent\\includegraphics[width=\\textwidth]{{{path}}}\n'
    
    content = md_formatting(content)

    return content


def md_to_tex_document(parsed: list) -> Document:
    doc = Document()
    content = ''
    placed_drop_cap = False
    center_count = 0

    for mde in parsed:
        if mde.type == MarkdownType.TITLE:
            doc.title = mde.value
            doc.out_file = mde.value
        elif mde.type == MarkdownType.CENTER:
            if center_count == 0:
                value = md_formatting(mde.value)
                lines = value.splitlines(False)
                value = '\\\n'
                for l in lines:
                    if len(l.strip()) > 0:
                        value += f'{l}\\\\\n'
                doc.subtitle = value
            else:
                if content.endswith('\\\\'):
                    content = content[:-2]
                value = mde.value.replace('\n \n', '\\\\\n')
                content += f"\\begin{{poetry}}\n{value}\n\\end{{poetry}}\n\n\n"
            center_count += 1
        elif mde.type == MarkdownType.PAR:
            if not placed_drop_cap:
                words = mde.value.replace('\t', ' ').split(' ')
                words = list(filter(lambda x: len(x) > 0, words))
                if len(words) > 0:
                    dropcap = words[0][0]
                    dropword = words[0][1:]
                    content += f'\\lettrine[lines={int(DROP_CAP_SIZE)}, findent=3pt, nindent=0pt]{{{dropcap}}}{{{dropword}}} ' + (' '.join(words[1:]) + '\\\\')
                    placed_drop_cap = True
            else:
                content += f'\\indent {mde.value}\\\\'
    
    doc.contents = md_formatting(content)

    return doc

def get_authors(authors_dict: dict):
    authors = []
    for key, value in authors_dict.items():
        authors.append(f'\\textit{{{key}}} {", ".join(value)}')

    return ' \\and '.join(authors)

def build_pdf(document: Document):
    template = slurp_file(TEMPLATE_FILE)
    out_file = document.out_file + '.tex'
    out_safe_file = f'"{out_file}"'

    content = template.replace('%{title}%', document.title)
    content = content.replace('%{subtitle}%', document.subtitle)
    content = content.replace('%{author}%', document.author)
    
    img_folders = ''
    for f in document.img_folders:
        img_folders += f'{{{f}}}'
    content = content.replace('%{img_folders}%', img_folders)
    
    if document.toc:
        content = content.replace('%{toc}%', '\\newpage\n\\tableofcontents\n\\newpage')
    content = content.replace('%{content}%', document.contents)

    with open(out_file, 'w') as f:
        print(f, content)
    
    res = subprocess.run(BUILD_COMMAND % out_safe_file, shell=True)
    if res.returncode == 0:
        res = subprocess.run(BUILD_COMMAND % out_safe_file, shell=True) # index
    if res.returncode != 0:
        panic("\n\n===================\nCould not compile!!\n===================\n\n")

def build_single(path: str):
    build_pdf(md_to_tex_document(parse_md_source(slurp_file(path))))

def build_all():
    fabulae = {}
    files = os.listdir(FABULAE_DIR)

    for f in files:
        if f.endswith(".md"):
            fabulae[f.replace('.md', '')] = md_to_tex_source(parse_md_source(slurp_file(f"{FABULAE_DIR}/{f}")))
    # fabulae = list(map(lambda x: x[1], sorted(fabulae.items())))                                   # sort by title
    fabulae = list(sorted(map(lambda x: x[1], fabulae.items()), key=lambda x: len(x.split(' '))))  # sort by length

    content = '\n\clearpage'.join(fabulae)
    doc = Document('Fābulae Vespertīnae',
        'Fābulae puerīs latīnē scrīptae',
        get_authors(json.loads(slurp_file(CONTRIB_FILE))),
        True,
        content,
        [FABULAE_DIR],
        'FābulaeVespertīnae')

    build_pdf(doc)


########## MAIN ##########

def main():
    if len(argv) > 1:
        for arg in argv[1:]:
            build_single(arg)
    else:
        build_all()

if __name__ == '__main__':
    main()