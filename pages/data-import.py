#######################
# imports & cofig
#######################
# imports
from utils.imports import (st, sst, requests, urllib, datetime, pd, io, re, os, io, re, os, Image, tiff, annotated_text, key, base64, imagecodecs, html, copy, alt, np, go)
import utils.func as fn
from utils.funcKadi import (kadiLoadFiles, kadiGetData, kadiGetUserRecords, kadiGetGroupRecords, getMetadataValue)

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
# variables
#########################
standardFilenameCSV = 'summary[timestamp].csv'
standardFilenameNormalFile = 'normal.txt'
standardFilenameQuickFile = 'quick standard.txt'
standardFilenameStandardFile = 'summary standard.txt'


#########################
# display functions
#########################
# show kadi import
def showKadiImport():
    # not logged in
    if not sst.userLoggedIn:                    
        formPlaceholder = st.empty()
        with formPlaceholder.container():
            st.info('You are currently not logged in with Kadi4Mat. Other options will be available after login.', icon=':material/vpn_key_off:')
    # logged in        
    else:                    
        
            
        useExample = 0
        formPlaceholder = st.empty()
        with formPlaceholder.container():
            # user select how to browse for the records        
            browseTypes = ['Show my own records (includes shared private records)', 'Search by Kadi4Mat record id']
            st.write('1. Please choose the way you want to select the record from Kadi4Mat:')
            browseType = st.selectbox('Search for records:',browseTypes, label_visibility='collapsed')
            left, right = st.columns((1, 20))
            if browseType == browseTypes[0]:
                    # records of the user
                    if len(sst.userRecords) == 0: # check if records are already loaded
                        kadiGetUserRecords()
                    left.write('↳')
                    with right:
                        st.write('2. Please select your record:')
                        selectedRecord = st.selectbox('selectKadiRecordByName', sorted(sst.userRecords.values()), format_func=lambda x: "@" + str(x), disabled=(not sst.userLoggedIn), label_visibility='collapsed')
                        recordID = str({v: k for k, v in sst.userRecords.items()}.get(selectedRecord))
                    
            elif browseType == browseTypes[1]:
                left.write('↳')
                with right:
                    # record id input field
                    st.write(f'2. Please enter the persistent Kadi4Mat record id and hit {key("Enter", write=False)}:', unsafe_allow_html=True)
                    # input field for record id
                    recordID = st.text_input('kadirecordid', label_visibility='collapsed', disabled=(not sst.userLoggedIn))
            else:
                recordID = ''
                
            #submit = st.button('Get data from record', type='primary', disabled=(not sst.userLoggedIn))
            if st.button('Get data from record', type='primary', disabled=(not sst.userLoggedIn)):
                sst.recordID = recordID
                sst.recordName = sst.userRecords[int(recordID)]
        kadiLoadFiles(formPlaceholder)

# show guf import
def showGufImport():
    # group @guf-ifg-epma
    st.write('Choose the desired record from the dropdown and enter the password for your record below.')
    
    formPlaceholder = st.empty()
    with formPlaceholder.container():      
        # records of group @guf-ifg-epma
        if len(sst.userRecords) == 0: # check if records are already loaded
            kadiGetGroupRecords()
        
        st.write('1. Please select your record:')
        selectedRecord = st.selectbox('selectKadiRecordByName', sorted(sst.userRecords.values()), format_func=lambda x: "@" + str(x), label_visibility='collapsed')
        recordID = str({v: k for k, v in sst.userRecords.items()}.get(selectedRecord))
        left, right = st.columns((1, 20))
        left.write('↳')
        with right:
            # pwd input field
            st.write('2. Please enter the password for your record:', unsafe_allow_html=True)
            pwdUser = str(st.text_input('pwduser', label_visibility='collapsed', type='password', max_chars=12))
        
        if st.button('Get data from record', type='primary'):
            sst.recordID = recordID
            sst.recordName = sst.userRecords[int(recordID)]
            sst.pwdUser = pwdUser            
            response = kadiGetData('records/' + str(sst.recordID) + '/extras/export/json')
            pwdKadi = getMetadataValue(response.json(), 'password')
            if pwdKadi == '':
                st.error('This record is currently not accessible via password. Please contact lab head to gain access.', icon=':material/no_accounts:')
            elif sst.pwdUser != pwdKadi:
                st.error('You have entered the wrong password, please try again.', icon=':material/vpn_key_alert:')
            else:
                kadiLoadFiles(formPlaceholder)


#########################
# sidebar
#########################
fn.renderSidebar('menuRedirect')


#########################
# data import
#########################
st.title('Data Import', anchor=False)  
   
if sst.userType == 'ag':
    st.subheader('Get EPMA records from the IfG GUF from Kadi4Mat', anchor=False)
elif sst.userType == 'kadi':
    st.subheader('Get your own EPMA records from your Kadi4Mat account', anchor=False)


# check if data is already loaded
if sst.kadiLoaded:
    st.success('Files already uploaded, check out **' + fn.pageNames['viewer']['name'] + '** in the sidebar menu.', icon=':material/data_check:')
    st.info('Do you want to reload another dataset? You can clear all loaded data in the sidebar menu.', icon=':material/question_exchange:')
else:
    if sst.userType == 'ag':
        showGufImport()
    elif sst.userType == 'kadi':
        showKadiImport()
    else:
        st.switch_page('main.py')