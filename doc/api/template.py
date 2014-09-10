#!/usr/bin/env python3
import os.path


MODULES = [
    'app',
    'bandwidth',
    'body',
    'builder',
    'cache',
    'collections',
    'connection',
    'converter',
    'cookie',
    'database',
    'debug',
    'decompression',
    'dns',
    'document',
    'document.base',
    'document.css',
    'document.html',
    'document.htmlparse',
    'document.htmlparse.base',
    'document.htmlparse.element',
    'document.htmlparse.html5lib_',
    'document.htmlparse.lxml_',
    'document.javascript',
    'document.sitemap',
    'document.util',
    'document.xml',
    'engine',
    'errors',
    'factory',
    'hook',
    'http',
    'http.chunked',
    'http.client',
    'http.redirect',
    'http.request',
    'http.robots',
    'http.stream',
    'http.proxy',
    'http.util',
    'http.web',
    'item',
    'namevalue',
    'observer',
    'options',
    'phantomjs',
    'processor',
    'processor.base',
    'processor.rule',
    'processor.phantomjs',
    'processor.web',
    'proxy',
    'recorder',
    'regexstream',
    'robotstxt',
    'scraper',
    'scraper.base',
    'scraper.css',
    'scraper.html',
    'scraper.sitemap',
    'scraper.util',
    'stats',
    'string',
    'url',
    'urlfilter',
    'util',
    'version',
    'waiter',
    'warc',
    'wrapper',
    'writer',
]


def main():
    for name in MODULES:
        path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '{0}.rst'.format(name)
        )
        with open(path, 'w') as out_file:
            out_file.write('.. This document was automatically generated.\n')
            out_file.write('   DO NOT EDIT!\n\n')

            title = ':mod:`{0}` Module'.format(name)
            out_file.write(title + '\n')
            out_file.write('=' * len(title) + '\n\n')
            out_file.write('.. automodule:: wpull.{0}\n'.format(name))
            out_file.write('    :members:\n')
            out_file.write('    :show-inheritance:\n')
            out_file.write('    :private-members:\n')
            out_file.write('    :special-members:\n')
            out_file.write('    :exclude-members: __dict__,__weakref__\n')


if __name__ == '__main__':
    main()
