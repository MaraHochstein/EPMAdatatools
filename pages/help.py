#######################
# imports & cofig
#######################
# imports
from utils.imports import (st, sst, OAuth2Component, requests, urllib, datetime, pd, io, re, os, io, re, os, Image, tiff, base64, imagecodecs, html, copy, alt, np, go)
import utils.func as fn

#page config
st.set_page_config(page_title='EPMA Data Tools', page_icon='./app/static/logo.png', layout='wide', initial_sidebar_state='expanded')

# check session state
fn.checkSessionState()

# refresh oauth token if logged in
fn.refreshOauthToken()


#######################
# css
#######################
fn.loadCSS()


#########################
# sidebar
#########################
fn.renderSidebar('menu')

#######################
# Info & Contact
#######################
st.title('Support', anchor=False)
st.subheader('Help', anchor=False)
st.info('If the site gets stuck after login or deleting and re-importing another dataset, clearing streamlits cache may help.', icon=':material/chat_info:')
st.button('Clear Streamlit Cache', on_click = fn.clearStCache, type = 'secondary')
    
st.write('')
st.info('For details on record and file naming read our documentation', icon=':material/article_shortcut:')
st.link_button('Read the documentation', 'https://hezel2000.quarto.pub/mag4/microprobe/data-access/kadi-upload.html')

st.subheader('Contact', anchor=False)
st.write('If you have any questions or want to provide feedback about EPMA Data Tools, please use this Email for contact: dominik.hezel - at - em.uni-frankfurt.de.')
st.link_button('Browse or Open an Issue on GitHub', 'https://github.com/MaraHochstein/EPMAdatatools/issues')

## testing
#fn.showSessionState()