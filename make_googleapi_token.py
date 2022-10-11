from __future__ import print_function
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/drive',
          'https://mail.google.com/']


def get_creds(fname, credfile):
    flow = InstalledAppFlow.from_client_secrets_file(credfile,
                                                     SCOPES)

    creds = flow.run_local_server(port=59591,
    authorization_prompt_message='Please visit this URL: {url}')

    with open(fname, 'wb') as token:
        pickle.dump(creds, token)


