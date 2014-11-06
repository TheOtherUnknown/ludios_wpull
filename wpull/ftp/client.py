'''FTP client.'''
import io

from trollius import From, Return
import trollius

from wpull.abstract.client import BaseClient, BaseSession
from wpull.body import Body
from wpull.ftp.command import Commander
from wpull.ftp.ls.parse import ListingParser
from wpull.ftp.request import Response, Command, ListingResponse
from wpull.ftp.stream import ControlStream
from wpull.ftp.util import FTPServerError, ReplyCodes
import wpull.ftp.util


class Client(BaseClient):
    '''FTP Client.

    The session object is :class:`Session`.
    '''
    def _session_class(self):
        return Session


class Session(BaseSession):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._connection = None
        self._control_stream = None
        self._commander = None
        self._request = None

        # TODO: recorder
        # TODO: maybe keep track of sessions among connections to avoid
        # having to login over and over again

    @trollius.coroutine
    def _init_stream(self, request):
        '''Create streams and commander.

        Coroutine.
        '''
        assert not self._connection
        self._connection = yield From(self._connection_pool.check_out(
            request.url_info.hostname, request.url_info.port))
        self._control_stream = ControlStream(self._connection)
        self._commander = Commander(self._control_stream)
        self._request = request

        if self._recorder_session:
            def control_data_callback(direction, data):
                assert direction in ('command', 'reply'), \
                    'Expect read/write. Got {}'.format(repr(direction))

                if direction == 'reply':
                    self._recorder_session.response_control_data(data)
                else:
                    self._recorder_session.request_control_data(data)

            self._control_stream.data_observer.add(control_data_callback)

    @trollius.coroutine
    def _log_in(self):
        '''Connect and login.

        Coroutine.
        '''
        # TODO: grab defaults from options
        username = self._request.url_info.username or 'anonymous'
        password = self._request.url_info.password or '-wpull@'

        yield From(self._commander.reconnect())
        yield From(self._commander.login(username, password))

    @trollius.coroutine
    def fetch(self, request, file=None, callback=None):
        '''Fetch a file.

        Returns:
            .ftp.request.Response

        Coroutine.
        '''
        response = Response()

        yield From(self._prepare_fetch(request, response, file, callback))

        reply = yield From(self._fetch_with_command(
            Command('RETR', request.url_info.path), response.body
        ))

        self._clean_up_fetch(response, reply)

        raise Return(response)

    @trollius.coroutine
    def fetch_file_listing(self, request, file=None, callback=None):
        '''Fetch a file listing.

        Returns:
            .ftp.request.ListingResponse

        Coroutine.
        '''
        response = ListingResponse()

        yield From(self._prepare_fetch(request, response, file, callback))

        try:
            reply = yield From(self._get_machine_listing(request, response))
        except FTPServerError as error:
            response.body.seek(0)
            response.body.truncate()
            if error.reply_code in (ReplyCodes.syntax_error_command_unrecognized,
                                    ReplyCodes.command_not_implemented):
                reply = yield From(self._get_list_listing(request, response))
            else:
                raise

        self._clean_up_fetch(response, reply)

        raise Return(response)

    @trollius.coroutine
    def _prepare_fetch(self, request, response, file=None, callback=None):
        '''Prepare for a fetch.

        Coroutine.
        '''

        yield From(self._init_stream(request))

        request.address = self._connection.address

        if self._recorder_session:
            self._recorder_session.begin_control(request)

        yield From(self._log_in())

        response.request = request

        if callback:
            file = callback(request, response)

        if not isinstance(file, Body):
            response.body = Body(file)
        else:
            response.body = file

        if self._recorder_session:
            self._recorder_session.pre_response(response)

    def _clean_up_fetch(self, response, reply):
        '''Clean up after a fetch.'''
        response.body.seek(0)
        response.reply = reply

        if self._recorder_session:
            self._recorder_session.response(response)

        if self._recorder_session:
            self._recorder_session.end_control(response)

    @trollius.coroutine
    def _fetch_with_command(self, command, file=None):
        '''Fetch data through a data connection.

        Coroutine.
        '''
        # TODO: the recorder needs to fit inside here
        data_connection = None
        data_stream = None

        @trollius.coroutine
        def connection_factory(address):
            nonlocal data_connection
            data_connection = yield From(
                self._connection_pool.check_out(address[0], address[1]))
            raise Return(data_connection)

        try:
            data_stream = yield From(self._commander.setup_data_stream(
                connection_factory
            ))

            if self._recorder_session:
                def data_callback(action, data):
                    if action == 'read':
                        self._recorder_session.response_data(data)

                data_stream.data_observer.add(data_callback)

            reply = yield From(self._commander.read_stream(
                command, file, data_stream
            ))

            raise Return(reply)
        finally:
            if data_stream:
                data_stream.data_observer.clear()

            if data_connection:
                data_connection.close()
                self._connection_pool.check_in(data_connection)

    @trollius.coroutine
    def _get_machine_listing(self, request, response):
        '''Request a MLSD.

        Coroutine.
        '''
        reply = yield From(self._fetch_with_command(
            Command('MLSD', request.url_info.path), response.body
        ))

        response.body.seek(0)

        listings = wpull.ftp.util.parse_machine_listing(
            response.body.read().decode('latin-1'),
            convert=True, strict=False
            )

        response.files = listings

        raise Return(reply)

    @trollius.coroutine
    def _get_list_listing(self, request, response):
        '''Request a LIST listing.

        Coroutine.
        '''
        reply = yield From(self._fetch_with_command(
            Command('LIST', request.url_info.path), response.body
        ))

        response.body.seek(0)

        file = io.TextIOWrapper(response.body, encoding='latin-1')

        listing_parser = ListingParser(file=file)
        listing_parser.run_heuristics()

        listings = listing_parser.parse()

        # We don't want the file to be closed when exiting this function
        file.detach()

        response.files = listings

        raise Return(reply)

    def clean(self):
        if self._connection:
            self._connection_pool.check_in(self._connection)

    def close(self):
        if self._connection:
            self._connection.close()
