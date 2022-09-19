import hashlib
from functools import wraps
import pandas as pd
import numpy as np
import scipy.stats as stats

from flask import (Flask,
                   render_template)
from flask import request, Response
app = Flask(__name__)


userhash = 'a90e6e60079f5e07d02541384fa95a9aec31144ad3a5f4b46e22bc0c38623624'
passwdhash = '09ff6bdc2e8bce7fc2abc5a909fcf059a0a99ec7f9717ddba869d003bdf38e51'

def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    uname_enc = hashlib.sha256(bytes(username, encoding='utf-8')).hexdigest()
    pword_enc = hashlib.sha256(bytes(password, encoding='utf-8')).hexdigest()
    return uname_enc == userhash and pword_enc == passwdhash


def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Could not verify your access level for that URL. You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


@app.route('/pbe_rankings.html')
@requires_auth
def vis():
    return render_template('rankings.html')


@app.route('/ranking_data', methods=["GET", "POST"])
def get_rankings():
    df = pd.read_csv('test_scores.csv').fillna('')
    zscored = [stats.mstats.zscore(df['judge_%d' % d]) for d in range(1, 8)]
    for d in range(1, 8):
        df['judge_%d_zscored' % d] = zscored[d - 1]
    avg_zscores = [np.mean([df[['judge_%d_zscored' % d]].iloc[i]  for d in range(1, 8)]) for i in range(len(df))]

    df['avg_zscore'] = avg_zscores

    overall_ranks = len(df) - np.argsort(avg_zscores).argsort()

    df['overall_rank'] = overall_ranks

    df['category_rank'] = np.zeros_like(df['overall_rank'])

    categories = np.unique(df['category'])

    for c in categories:
        iscat = df['category'] == c
        dfcat = df[iscat]
        cat_zscores = dfcat['avg_zscore']
        category_ranks = len(dfcat) - np.argsort(cat_zscores).argsort() 
        df.loc[iscat, 'category_rank'] = category_ranks

    category_winners = df[df['category_rank'] == 1]

    return {"rankings": df.to_html(),
            "winners": category_winners.to_html()}
    
if __name__ == "__main__":
    #app.run(ssl_context='adhoc')
    app.run(ssl_context=('cert.pem', 'key.pem'))
