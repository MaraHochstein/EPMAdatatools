#######################
# imports & cofig
#######################
# imports
from utils.imports import (st, sst, requests, urllib, datetime, pd, io, re, os, io, re, os, Image, tiff, base64, imagecodecs, html, copy, alt, np, go) #, annotated_text, key
import utils.func as fn
from utils.funcKadi import kadiLoadFiles

from streamlit_oauth import OAuth2Component # oauth button component

# kadi doesn't support the default httpx_oauth 0.15.1 method 'client_secret_basic' so we define a custom component (see issue #33)
class kadiOAuth2Component(OAuth2Component):
    def __init__(self, *args, token_endpoint_auth_method='client_secret_post', **kwargs):
        # call original __init__ with modified parameter
        super().__init__(*args, token_endpoint_auth_method=token_endpoint_auth_method, **kwargs)

# use new kadiComponent here
oauth2 = kadiOAuth2Component(
    client_id = st.secrets['oauthClientID'],
    client_secret = st.secrets['oauthClientSecret'],
    authorize_endpoint = 'https://kadi4mat.iam.kit.edu/oauth/authorize',
    token_endpoint = 'https://kadi4mat.iam.kit.edu/oauth/token',
    refresh_token_endpoint = 'https://kadi4mat.iam.kit.edu/oauth/token',
    revoke_token_endpoint = 'https://kadi4mat.iam.kit.edu/oauth/revoke',
)

kadiApiBaseURL = 'https://kadi4mat.iam.kit.edu'

# set up variables in session_state
fn.initSessionState()

#page config
st.set_page_config(page_title='EPMA Data Tools', page_icon='./app/static/logo.png', layout='wide', initial_sidebar_state='expanded')

# refresh oauth token if logged in
fn.refreshOauthToken()


#######################
# css (page-only)
#######################
fn.loadCSS()

# increase height for buttons on start page only
st.html(
    """
<style>
[data-testid=stBaseButton-primary] {
    height: auto;
    padding-top: 7px !important;
    padding-bottom: 7px !important;
    border: none;
    border-radius: 5px;
    background-color: white;
    color: black;
}

[data-testid=stBaseButton-primary] [data-testid=stMarkdownContainer] > p {
                font-size: 1.2rem;
                font-weight: 1000;
}


</style>
"""
)


#########################
# welcome page
#########################  
st.title('Welcome to EPMA Data Tools', anchor=False)

# Info
st.header('What is EPMA Data Tools?', anchor=False)
st.write('The tool helps to process raw data from an EPMA (Electron Probe Microanalyzer), merges several files into one standardised output file and makes it possible to perform various analyses such as filtering, mineral formula calculation and data visualisation.')
st.info('Note: The tool is currently limited to data processing from the EPMA "JEOL JXA-8530F Plus Hyperprobe". Integration of other EPMA models may be added in the future.')
st.divider()

col1, col2, col3 = st.columns(3)

# Demo version
with col1:
    if st.button('Start with Demo', 
        help='Load our preconfigured dataset to have a look at the functions of EPMA Data Tools!', 
        icon=':material/rocket_launch:',
        type='primary', use_container_width=True):
            if sst.userType == 'kadi':
                fn.kadiLogout()
                sst['userRecords'] = {}
            if sst.userType == 'ag':
                sst['userRecords'] = {}
            sst.userType = 'demo'
            sst.recordID = '39868' #@guf-ifg-epma-20231224-demo-quant
            sst.recordName = 'guf-ifg-epma-20231224-demo-quant'
            kadiLoadFiles()
# PW required
with col2:
    if st.button('Access records from the IfG GUF', 
        help='Click this to browse the EPMA records of the Institute for Geosciences of the Goethe University Frankfurt.  \nYou may need a password to load the data of the records.', 
        icon=':material/passkey:',
        type='primary', use_container_width=True):
            if sst.userType == 'kadi':
                fn.kadiLogout()
                sst['userRecords'] = {}
            sst.userType = 'ag'
            st.switch_page('pages/data-import.py')
# Kadi login
with col3:
    # Oauth Authoriziation Button for Kadi (oauth2 Component)
    if not sst.userLoggedIn:
        if sst.userType == 'ag':
            sst['userRecords'] = {}
        result = oauth2.authorize_button(
            name='Login with Kadi4Mat',
            icon='https://kadi4mat.readthedocs.io/en/stable/_static/favicon.ico',
            redirect_uri= st.secrets['oauthRedirectUri'] + 'component/streamlit_oauth.authorize_button',
            scope='',
            key='kadi',
            extras_params={'response_type':'code'},
            pkce='S256',
            use_container_width=True,
            auto_click=False
            )
        if result:
            # set tokens
            sst.kadiPAT = result['token']['access_token']        
            sst.kadiRefreshToken = result['token']['refresh_token']
            if 'expires_in' in result['token']:
                sst.kadiTokenRefreshTime = datetime.datetime.now() +  datetime.timedelta(seconds=(result['token']['expires_in']-120))
            else:
                sst.kadiTokenRefreshTime = datetime.datetime.now() +  datetime.timedelta(seconds=(3600-120))
            
            # get user details
            userResponse = requests.get(kadiApiBaseURL + '/api/users/me', headers={'Authorization': 'Bearer ' + sst.kadiPAT})
            sst.kadiUserID = userResponse.json()['id']
            sst.kadiUserName = userResponse.json()['displayname']
            if not sst.userLoggedIn:
                sst.infoToast['txt'] = 'You are successfully logged in with Kadi4Mat as ' + sst.kadiUserName + '.'
                sst.infoToast['ico'] = ':material/how_to_reg:'
            sst.userLoggedIn = True
            sst.userType = 'kadi'
            st.switch_page('pages/data-import.py')
    else:
        st.button('Log out',type='primary', icon=':material/logout:', use_container_width=True, on_click=fn.kadiLogout, key='kadilogout')

st.divider()

# NFDI4Earth
st.markdown('<a href="https://nfdi4earth.de/" target="_blank"><img src="./app/static/logo-nfdi4earth.png" height="65" style="margin-bottom: 5px;"></a>',unsafe_allow_html=True)
st.write('EPMA Data Tools is part of the [NFDI4Earth](https://nfdi4earth.de/) pilot-project "Developing Tools and FAIR Principles for the MetBase Database". NFDI4Earth is funded by the German Research Foundation (DFG project no. 460036893).')
#annotated_text('EPMA Data Tools is part of the ', ('[NFDI4Earth](https://nfdi4earth.de/)', ':link:', 'rgba(111, 184, 255, 0.24)'), ' pilot-project "Developing Tools and FAIR Principles for the MetBase Database". NFDI4Earth is funded by the German Research Foundation (DFG project no. 460036893).')

#################
#  sidebar
#################
# important: render menu() after userType-buttons above
fn.renderSidebar('menu')