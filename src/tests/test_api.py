import unittest
from unittest import mock

from gobstuf.api import _health, _routed_url, _update_response, _update_request
from gobstuf.api import _get_stuf, _post_stuf, _stuf, _handle_stuf_request
from gobstuf.api import get_app, run
from werkzeug.exceptions import BadRequest, MethodNotAllowed

class MockResponse:

    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code


class TestAPI(unittest.TestCase):

    def setUp(self) -> None:
        pass

    def test_health(self):
        result = _health()
        self.assertEqual(result, "Connectivity OK")

    def test_routed_url(self):
        result = _routed_url("proto://domain/path?args")
        self.assertEqual(result, "ROUTE_SCHEME://ROUTE_NETLOC/path?args")

        result = _routed_url("proto://domain/path?wsdl")
        self.assertEqual(result, "ROUTE_SCHEME://ROUTE_NETLOC/path?wsdl")

        result = _routed_url("proto://domain/path/?wsdl")
        self.assertEqual(result, "ROUTE_SCHEME://ROUTE_NETLOC/path?wsdl")

    def test_update_response(self):
        result = _update_response("text")
        self.assertEqual(result, "text")

        expect = "...localhost:GOB_STUF_PORT..."

        result = _update_response("...ROUTE_NETLOC...")
        self.assertEqual(result, expect)

        for n in [80, 800, 1234, 10000]:
            result = _update_response(f"...ROUTE_NETLOC:{n}...")
            self.assertEqual(result, expect)

        for n in [0, 123456]:
            result = _update_response(f"...ROUTE_NETLOC:{n}...")
            self.assertNotEqual(result, expect)

    def test_update_request(self):
        result = _update_request("...localhost:GOB_STUF_PORT...")
        self.assertEqual(result, "...ROUTE_NETLOC...")

        # Only convert full references
        result = _update_request("...localhost...")
        self.assertEqual(result, "...localhost...")


    @mock.patch("gobstuf.api.cert_get")
    def test_get_stuf(self, mock_get):
        mock_get.return_value = "get"

        response = _get_stuf("any url")
        self.assertEqual(response, "get")
        mock_get.assert_called_with("any url")

    @mock.patch("gobstuf.api.cert_post")
    def test_post_stuf(self, mock_post):
        mock_post.return_value = "post"

        url = "any url"
        data = "any data"
        headers = {
            "Soapaction": "Any action",
            "Content-Type": "text/xml",
            "Any other": "Any value"
        }
        expect_headers = {
            "Soapaction": "Any action",
            "Content-Type": "text/xml"
        }

        response = _post_stuf(url, data, headers)
        self.assertEqual(response, "post")
        mock_post.assert_called_with(url, data=data, headers=expect_headers)

        for h in [{},
                  {"Soapaction": "Any action"},
                  {"Soapaction": "Any action", "Content-Type": "any type"},
                  ]:
            with self.assertRaises(BadRequest):
                headers = h
                response = _post_stuf(url, data, headers)

    @mock.patch("gobstuf.api._get_stuf")
    @mock.patch("gobstuf.api._post_stuf")
    @mock.patch("gobstuf.api._update_request")
    def test_handle_stuf_request(self, mock_update_request, mock_post_stuf, mock_get_stuf):
        routed_url = 'routed url'

        request = type('MockGet', (object,), {'method': 'GET'})
        self.assertEqual(mock_get_stuf.return_value, _handle_stuf_request(request, routed_url))
        mock_get_stuf.assert_called_with(routed_url)

        request = type('MockPost', (object,), {'method': 'POST', 'data': mock.MagicMock(), 'headers': 'headers'})
        self.assertEqual(mock_post_stuf.return_value, _handle_stuf_request(request, routed_url))
        mock_post_stuf.assert_called_with(routed_url, mock_update_request.return_value, request.headers)

        request = type('MockInvalidMethod', (object,), {'method': 'INVALID'})
        with self.assertRaisesRegexp(MethodNotAllowed, '405 Method Not Allowed'):
            _handle_stuf_request(request, routed_url)


    @mock.patch("gobstuf.api.AuditLogger")
    @mock.patch("gobstuf.api._handle_stuf_request", return_value=MockResponse('get', 123))
    @mock.patch("gobstuf.api.flask")
    @mock.patch("gobstuf.api.uuid.uuid4", return_value="the uuid")
    def test_stuf(self, mock_uuid, mock_flask, mock_handle_stuf, mock_audit_logger):
        mock_flask.request.method = 'GET'
        mock_flask.request.url = "any url"
        mock_flask.request.data = b"any data"
        mock_flask.request.headers = {
            'Soapaction': 'zeepactie',
        }
        mock_flask.request.remote_addr = '1.2.3.4'

        response = _stuf()
        self.assertEqual(response.data, b"get")

        # Make sure audit log is called
        audit_logger_instance = mock_audit_logger.get_instance.return_value
        audit_logger_instance.log_request.assert_called_with(
            '1.2.3.4',
            'ROUTE_SCHEME://ROUTE_NETLOC/any url',
            {
                'soapaction': 'zeepactie',
                'original_url': 'any url',
                'method': 'GET',
            },
            'the uuid',
        )

        audit_logger_instance.log_response.assert_called_with(
            '1.2.3.4',
            'ROUTE_SCHEME://ROUTE_NETLOC/any url',
            {
                'soapaction': 'zeepactie',
                'remote_response_code': 123,
                'original_url': 'any url',
                'method': 'GET',
            },
            'the uuid',
        )

    @mock.patch("gobstuf.api.AuditLogger")
    @mock.patch("gobstuf.api._handle_stuf_request", return_value=MockResponse('get', 123))
    @mock.patch("gobstuf.api.flask")
    @mock.patch("gobstuf.api.uuid.uuid4", return_value="the uuid")
    def test_stuf_exception(self, mock_uuid, mock_flask, mock_handle_stuf, mock_audit_logger):
        mock_handle_stuf.side_effect = BadRequest("Exception message")

        mock_flask.request.method = 'GET'
        mock_flask.request.url = "any url"
        mock_flask.request.data = b"any data"
        mock_flask.request.headers = {
            'Soapaction': 'zeepactie',
        }
        mock_flask.request.remote_addr = '1.2.3.4'

        with self.assertRaises(BadRequest):
            response = _stuf()

        # Make sure audit log is called
        audit_logger_instance = mock_audit_logger.get_instance.return_value
        audit_logger_instance.log_request.assert_called_with(
            '1.2.3.4',
            'ROUTE_SCHEME://ROUTE_NETLOC/any url',
            {
                'soapaction': 'zeepactie',
                'original_url': 'any url',
                'method': 'GET',
            },
            'the uuid',
        )

        audit_logger_instance.log_response.assert_called_with(
            '1.2.3.4',
            'ROUTE_SCHEME://ROUTE_NETLOC/any url',
            {
                'soapaction': 'zeepactie',
                'exception': '400 Bad Request: Exception message',
                'original_url': 'any url',
                'method': 'GET',
            },
            'the uuid',
        )

    @mock.patch("gobstuf.api.CORS", mock.MagicMock())
    @mock.patch("gobstuf.api.Flask")
    def test_get_app(self, mock_flask):
        mock_app = mock.MagicMock()
        mock_flask.return_value = mock_app
        app = get_app()
        mock_flask.assert_called()
        mock_app.route.assert_called()

    @mock.patch("gobstuf.api.GOB_STUF_PORT", 1234)
    @mock.patch("gobstuf.api.get_app")
    def test_run(self, mock_get_app):
        mock_app = mock.MagicMock()
        mock_get_app.return_value = mock_app
        run()
        mock_app.run.assert_called_with(port=1234)

