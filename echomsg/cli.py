import sys
import os
import argparse
import logging
import traceback

from jinja2.exceptions import TemplateNotFound
import jinja2

import echomsg
from echomsg import MessagesRegistry, parseFile, formatConstant, DescriptionError, set_default_language


logger = logging.getLogger("echomsg")

def render_language(language, extension, registry, outdir, basename):
    loader = jinja2.FileSystemLoader(os.path.join(os.path.dirname(echomsg.__file__), "templates"))
    env = jinja2.Environment(loader=loader)
    env.filters["constant"] = lambda x: formatConstant(x, language=language)
    template = env.get_template('{}.tpl'.format(language))

    set_default_language(language)
    
    context = {}
    context['basename'] = basename
    context['namespace'] = registry.namespace
    context['registry'] = registry

    if not outdir is None:
        if not os.path.exists(outdir):
            os.makedirs(outdir)
        with open(os.path.join(outdir, "{}.{}".format(context['basename'], extension)), "w") as out:
            out.write(template.render(context))

def main():

    logger.addHandler(logging.StreamHandler())

    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('files', metavar='file', type=str, nargs='+',
                        help='Message files to process')

    parser.add_argument("--debug", "-d", default=False, help="Backup backend", required=False, action='store_true')

    parser.add_argument('-p', metavar='paths', type=str, action='append', default=[],
                        help='Message files to process', dest='paths')

    parser.add_argument('--python-outdir', metavar='dir', type=str,
                        help='Output directory for Python files', dest='outdir_python')

    parser.add_argument('--cpp-outdir', metavar='dir', type=str,
                        help='Output directory for C++ files', dest='outdir_cpp')

    args = parser.parse_args()

    args.paths.insert(0, os.path.join(os.path.dirname(echomsg.__file__), "messages"))
    args.paths.append(".")

    logger.setLevel(logging.INFO)

    if args.debug or check_debug:
        logger.setLevel(logging.DEBUG)

    for filename in args.files:
        logger.debug("Processing file %s", filename)
        registry = MessagesRegistry()
        registry.namespace = ''
        try:
            parseFile(filename, registry, args.paths)
        except DescriptionError as e:
            logger.error("Processing error: %s", e)
            sys.exit(1)

        logger.debug("Generating C++ wrapper")
        render_language("cpp", "h", registry, args.outdir_cpp, os.path.splitext(os.path.basename(filename))[0])
        logger.debug("Generating Python wrapper")
        render_language("python", "py", registry, args.outdir_python, os.path.splitext(os.path.basename(filename))[0])
