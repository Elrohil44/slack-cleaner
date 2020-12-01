import os
import webbrowser

from slack_sdk import WebClient
from slack_sdk.oauth import AuthorizeUrlGenerator
from slack_sdk.oauth.state_store import FileOAuthStateStore
from flask import Flask, request, make_response
from threading import Timer

from slack_cleaner.cleaner import start


client_secret = os.environ["SLACK_CLIENT_SECRET"]
client_id = os.environ["SLACK_CLIENT_ID"]
redirect_uri = "http://localhost:23001/slack/oauth"

authorize_url_generator = AuthorizeUrlGenerator(
        authorization_url="https://slack.com/oauth/authorize",
        client_id=client_id,
        scopes=["identify", "users:read", "channels:read", "groups:read", "mpim:read", "im:read", "channels:history","groups:history","mpim:history","im:history", "chat:write:bot"],
        user_scopes=["users:read", "channels:read", "channels:history", "chat:write", "groups:history", "groups:read", "im:history", "im:read", "mpim:history", "mpim:read"],
        redirect_uri=redirect_uri
    )

app = Flask(__name__)
server = None
token = None
args = None
state_store = FileOAuthStateStore(expiration_seconds=300, base_dir="./slack-cleaner-data")


@app.route("/slack/install", methods=["GET"])
def oauth_start():
    state = state_store.issue()
    url = authorize_url_generator.generate(state)
    return f'<a href="{url}">' \
           f'<img alt=""Add to Slack"" height="40" width="139" src="https://platform.slack-edge.com/img/add_to_slack.png" srcset="https://platform.slack-edge.com/img/add_to_slack.png 1x, https://platform.slack-edge.com/img/add_to_slack@2x.png 2x" /></a>'


@app.route("/slack/oauth", methods=["GET"])
def oauth_callback():
    # Retrieve the auth code and state from the request params
    if "code" in request.args:
        # Verify the state parameter
        if state_store.consume(request.args["state"]):
            client = WebClient()  # no prepared token needed for this
            # Complete the installation by calling oauth.v2.access API method
            oauth_response = client.oauth_access(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                code=request.args["code"]
            )

            token = oauth_response.get("access_token")
            Timer(0, lambda: start(token, args)).start()

            return "Thanks for installing this app!"
        else:
            return make_response(f"Try the installation again (the state value is already expired)", 400)

    error = request.args["error"] if "error" in request.args else ""
    return make_response(f"Something is wrong with the installation (error: {error})", 400)


def obtain_token_and_run(cmd_args):
    global args
    args = cmd_args
    Timer(0, lambda: app.run(port=23001)).start()
    webbrowser.open('http://localhost:23001/slack/install')

