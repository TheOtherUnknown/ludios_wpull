import codecs
import itertools
import asyncio
import logging
import sys

from wpull.backport.logging import BraceMessage as __
from wpull.database.base import AddURLInfo
from wpull.database.sqltable import GenericSQLURLTable
from wpull.pipeline.app import AppSession
from wpull.pipeline.pipeline import ItemTask
import wpull.util
import wpull.url


_logger = logging.getLogger(__name__)


class DatabaseSetupTask(ItemTask[AppSession]):
    @asyncio.coroutine
    def process(self, session: AppSession):
        if session.args.database_uri:
            session.factory.class_map[
                'URLTableImplementation'] = GenericSQLURLTable
            url_table_impl = session.factory.new(
                'URLTableImplementation', session.args.database_uri)
        else:
            url_table_impl = session.factory.new(
                'URLTableImplementation', path=session.args.database)

        url_table = session.factory.new('URLTable', url_table_impl)


class InputURLTask(ItemTask[AppSession]):
    @asyncio.coroutine
    def process(self, session: AppSession):
        url_table = session.factory['URLTable']

        for batch in wpull.util.grouper(self._read_input_urls(session), 1000):
            url_table.add_many(AddURLInfo(url_info.url, None, None) for url_info in batch if url_info)
            # TODO: attach hook for notifying progress

            # TODO: raise on error if no urls
            # urls = (line.strip() for line in input_file if line.strip())
            #
            # if not urls:
            #     raise ValueError(_('No URLs found in input file.'))
            #
            # return urls

    @classmethod
    def _read_input_urls(cls, session: AppSession, default_scheme='http'):
        '''Read the URLs provided by the user.'''

        url_string_iter = session.args.urls or ()
        # FIXME: url rewriter isn't created yet
        url_rewriter = session.factory.get('URLRewriter')

        if session.args.input_file:
            if session.args.force_html:
                lines = cls._input_file_as_html_links(session)
            else:
                lines = cls._input_file_as_lines(session)

            url_string_iter = itertools.chain(url_string_iter, lines)

        base_url = session.args.base

        for url_string in url_string_iter:
            _logger.debug(__('Parsing URL {0}', url_string))

            if base_url:
                url_string = wpull.url.urljoin(base_url, url_string)

            url_info = wpull.url.URLInfo.parse(
                url_string, default_scheme=default_scheme)

            _logger.debug(__('Parsed URL {0}', url_info))

            if url_rewriter:
                # TODO: this logic should be a hook
                url_info = url_rewriter.rewrite(url_info)
                _logger.debug(__('Rewritten URL {0}', url_info))

            yield url_info

    @classmethod
    def _input_file_as_lines(cls, session: AppSession):
        '''Read lines from input file and return them.'''
        if session.args.input_file == sys.stdin:
            input_file = session.args.input_file
        else:
            reader = codecs.getreader(session.args.local_encoding or 'utf-8')
            input_file = reader(session.args.input_file)

        return input_file

    @classmethod
    def _input_file_as_html_links(cls, session: AppSession):
        '''Read input file as HTML and return the links.'''
        scrape_result = session.factory['HTMLScraper'].scrape_file(
            session.args.input_file,
            encoding=session.args.local_encoding or 'utf-8'
        )

        for context in scrape_result.link_contexts:
            yield context.link
