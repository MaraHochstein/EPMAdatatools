#######################
# imports
#######################
from utils.imports import (st, sst, OAuth2Component, requests, urllib, datetime, pd, io, re, os, io, re, os, Image, tiff, base64, imagecodecs, html, copy, alt, np, go)


#######################
# variables
#######################
global variableList
variableList = [    
    # record variables
    ['recordID', ''],
    ['recordName', ''],
    
    ['kadiLoaded', False],
    ['kadiMetaData', pd.DataFrame()],
    
    ['imageFiles', {}],
    ['imageData', []],
    
    ['mapData', {}],
    ['mapGeneralData', {}],
    ['mapWdsData', {}],
    ['mapEdsData', {}],
    
    ['csvMerged', pd.DataFrame()],
    
    ['condElements', {}],
    ['condInfos', {}],
    ['condMapInfos', {}],
    ['condSamples', {}],
    ['condMapSamples', {}],
    ['condStd', {}],
    ['methodGeneralData', pd.DataFrame()],
    ['methodSampleData', pd.DataFrame()],
    ['methodStdData', pd.DataFrame()],
    ['shortMeasCond', dict()],
    
    ['standardsXlsx', dict()],
    ['standardsXlsxExport', {}],
    
    ['kadiFilter', {}],
    ['dataViewerFilter', dict()],
    ['csvMergedFiltered', pd.DataFrame()],
    
    ['mapFilter', {}],
    ['mapEditFilter', dict()],
    ['mapEdit', ''],
    ['mapImages', dict()],

    ['referenceDict', {}],
    ['selectedMinerals', []],
    ['csvMergedMinerals', pd.DataFrame()],
    
    # user Variables
    ['userType', None], # None / 'demo' / 'ag' / 'kadi'
    ['userLoggedIn', False],
    ['kadiPAT', ''],
    ['kadiRefreshToken', ''],
    ['kadiTokenRefreshTime', datetime.datetime.now()],
    ['kadiUserID', 0],
    ['kadiUserName',''],
    ['userRecords', {}],
    ['pwdUser',''], # guf password
    
    # other variables
    ['infoToast', {}], # messages for st.toast after switch_page
    ['createZipImg', 0], # for export btn
    ['createZipMap', 0], # for export btn
]

global pageNames
pageNames = {
        'home': {'name': 'Start & Login', 'ico': ':material/home:'},
        'import': {'name': 'Data Import', 'ico': ':material/add_notes:'},
        'viewer': {'name': 'View & Filter Data', 'ico': ':material/lab_research:'},
        'mineral': {'name': 'Mineral Identification', 'ico': ':material/diamond:'},
        'export': {'name': 'Data Export & Upload', 'ico': ':material/export_notes:'},
        'help': {'name': 'Contact', 'ico': ':material/contact_support:'},
        }

#####################
# session_state
#####################
# set up session_state
def initSessionState():
    for variable in variableList:
        saveVar(variable[0], variable[1])

# check session_state variables
def checkSessionState():
    for variable in variableList:
        if variable[0] not in sst:
            initSessionState()
            sst.infoToast['txt'] = 'Streamlit session-state had to be initialized again. You may need to reload your data.'
            sst.infoToast['ico'] = ':material/sync_problem:'
            st.switch_page('main.py')
        
    if 'userLoggedIn' not in sst:
        initSessionState()

# save variable in session_state
def saveVar(variableName, variable):
    if variableName not in sst:
        sst[variableName] = copy.deepcopy(variable)

# reset one session_state variable
def resetVar(variableName):
    sst[variableName] = [copy.deepcopy(variable[1]) for variable in variableList if variable[0] == variableName][0]
    
# reset session_state (Clear data button in sidebar)
def deleteSessionState():
    # delete all except auth variables
    keysDelete = [string for string in sst.keys() if string not in ['userLoggedIn','kadiPAT','kadiRefreshToken','kadiTokenRefreshTime','kadiUserID','kadiUserName','userRecords', 'userType']]
    for key in keysDelete:
        del sst[key]
    initSessionState()
    sst.infoToast['txt'] = 'All data cleared!'
    sst.infoToast['ico'] = ':material/delete:'

# clear streamlit cache
def clearStCache():
    st.cache_data.clear()
    sst.infoToast['txt'] = 'Cached data cleared! Please note, that loading the same dataset again may take more time.'
    sst.infoToast['ico'] = ':material/delete:'

# show session_state
def showSessionState():
    st.subheader('session_state')
    st.write(sst)


#####################
# toast
#####################
# show info toast if in sst & clear
def showInfoToast():
    if sst.infoToast != {}:
        toastTxt = sst.infoToast['txt']
        toastIco = sst.infoToast['ico']
        sst.infoToast = {}
        st.toast(toastTxt, icon=toastIco)


#####################
# sidebar
#####################
# menus
def menuSteps():
    #show menu entries based on role and loaded data
    st.sidebar.page_link('main.py', 
        icon = pageNames['home']['ico'],
        label = pageNames['home']['name'])
      
    if sst.userType in ['ag','kadi','demo']:
        st.sidebar.page_link('pages/data-import.py', 
            icon = pageNames['import']['ico'],
            label = pageNames['import']['name'],
            disabled = sst.userType == 'demo')
        st.sidebar.page_link('pages/data-viewer.py', 
            icon = pageNames['viewer']['ico'],
            label = pageNames['viewer']['name'],
            disabled = not(sst.kadiLoaded))
        st.sidebar.page_link('pages/mineral-identification.py', 
            icon = pageNames['mineral']['ico'],
            label = pageNames['mineral']['name'],
            disabled = not(sst.kadiLoaded))
        st.sidebar.page_link('pages/data-export.py', 
            icon = pageNames['export']['ico'],
            label = pageNames['export']['name'],
            disabled = not(sst.kadiLoaded))
    st.sidebar.page_link('pages/help.py',
            icon = pageNames['help']['ico'],
            label = pageNames['help']['name'])   

def menuBasic():
    # Show the basic menu
    st.sidebar.page_link('main.py', 
        icon = pageNames['home']['ico'],
        label = pageNames['home']['name'])
    st.sidebar.page_link('pages/help.py',
        icon = pageNames['help']['ico'],
        label = pageNames['help']['name'])

def menu():
    # Determine if a user is logged in or not, then show the correct
    # navigation menu
    if sst.userType is None:
        menuBasic()
        return
    menuSteps()

def menuRedirect():
    # Redirect users to the main page if not logged in, otherwise continue to
    # render the navigation menu
    if 'userType' not in sst or sst.userType is None:
        st.switch_page('main.py')
    menu()



# render sidebar & toast
def renderSidebar(menuType):
    # no relative path because sidebar is rendered from different dir
    st.logo(st.secrets['oauthRedirectUri'] + '~/+/app/static/transparent.png', icon_image='https://epmatools.streamlit.app/~/+/app/static/logo.png')
    
    with st.sidebar:
        if sst.userType == 'demo':
            left, right = st.columns((2,8))
            with left:
                st.title(':material/rocket_launch:')
            with right:
                st.title('Demo')
        elif sst.userType == 'ag':
            left, right = st.columns((4,6))
            with left:
                st.markdown('<img src="./app/static/logo-guf.png" height="45" style="margin-top: 20px; margin-left: 15px">',unsafe_allow_html=True)
            with right:
                st.header('EPMA records from the IfG GUF')
        elif sst.userType == 'kadi':
            left, right = st.columns((4,6))
            with left:
                st.markdown('<img src="./app/static/logo-kadi.png" height="30" style="margin-top: 15px; margin-left: 12px">',unsafe_allow_html=True)
            with right:
                if sst.userLoggedIn:
                    st.subheader('Logged in as:  \n_' + sst.kadiUserName + '_')
                else:
                    st.header('Not logged in')
        else:
            left, right = st.columns((4,6))
            with left:
                st.title('')
            with right:
                st.title('')
        st.divider()
    
    if menuType == 'menu':
        menu()
    else:
        menuRedirect()

    with st.sidebar:
        st.divider()
    
    # show info data loaded
    if sst.userType != None:
        with st.sidebar:
            if sst.kadiLoaded:
                if sst.recordName != '':
                    date, txt = sst.recordName.replace('guf-ifg-epma-','').split('-',1)
                    showName = f"{date[:4]}-{date[4:6]}-{date[6:]} {txt.replace('-',' ')}"
                    st.success(':material/check: **' + showName + '**' + (('  \n\n_' + sst.kadiMetaData.loc['Description', 'Value'].replace('guf-ifg-epma-','') + '_') if ('Description' in sst.kadiMetaData.index and sst.kadiMetaData.loc['Description', 'Value'] != '') else ''))
                elif sst.userType == 'demo':
                    st.success(':material/check: **Quantitative Demo Dataset**')          
            else:
                st.warning(':material/close: No dataset loaded')
            
    if sst.kadiLoaded:
        with st.sidebar:
            st.button('**Clear data**', icon=':material/delete:', use_container_width=True, on_click=deleteSessionState)
    
        with st.sidebar:
            st.divider()
    
    showInfoToast()
    

#####################
# OAuth
#####################
# refresh oauthToken
def refreshOauthToken():
    # only if token is expiring and has not expired yet
    try:
        # -> check session state
        if ('kadiRefreshToken' in sst and
            not sst.kadiRefreshToken == '' and
            datetime.datetime.now() >= sst.kadiTokenRefreshTime and
            datetime.datetime.now() <= (sst.kadiTokenRefreshTime + datetime.timedelta(seconds=120))): 
            # get access token
            tokenParams = {
                'grant_type': 'refresh_token',
                'client_id': st.secrets['oauthClientID'],
                'client_secret': st.secrets['oauthClientSecret'],
                'refresh_token': sst.kadiRefreshToken
            }
            tokenResponse = requests.post('https://kadi4mat.iam.kit.edu/oauth/token', data=tokenParams)
            sst.kadiPAT = tokenResponse.json()['access_token']
            sst.kadiRefreshToken = tokenResponse.json()['refresh_token']
    except Exception:
        st.warning('You are not logged in. Please authorize again with Kadi4Mat on the startpage.', icon=':material/vpn_key_off:')
        kadiLogout()

# reset auth variables
def kadiLogout():
    keysDelete = ['userLoggedIn','kadiPAT','kadiRefreshToken','kadiTokenRefreshTime','kadiUserID','kadiUserName', 'userRecords','userType']
    for key in keysDelete:
        del sst[key]
    clearStCache()
    initSessionState()
    sst.userType = 'demo'
    sst.infoToast['txt'] = 'Successfully logged out.'
    sst.infoToast['ico'] = ':material/digital_out_of_home:'      

    
#####################
# CSS
#####################
# add noLines number of newlines
def addLines(noLines):
    i = 0
    while i < noLines:
        st.write('')
        i += 1

# load custom css
def loadCSS():
    #####################################
    # hide menu on right side
    #####################################
    st.html(
    """
    <style>
    .st-emotion-cache-915phk, .e1obcldf17, ._link_gzau3_10, ._profileContainer_gzau3_53, ._profilePreview_gzau3_63 {
        display: none;
    }
    </style>
    """)
    
    
    #####################################
    # hide tracebacks in error messages
    #####################################
    st.html(
    """
    <style>
    .e1dl0tyv1, .e1dl0tyv0 {
        display: none;
    }
    </style>
    """)


    #####################################
    # iframe
    #####################################
    st.html(
    """
    <style>
    .iframe {
        margin-top: -10px;
        margin-bottom: -10px;
    }
    </style>
    """)


    #####################################
    # keyx
    #####################################
    st.html(
    """
    <style>
    .keyx {
        background-color: rgb(34, 36, 38);
            border-radius: 3px;
            border: 1px solid rgb(69, 75, 78);
            box-shadow: rgba(0, 0, 0, 0.2) 0px 1px 1px, rgba(24, 26, 27, 0.7) 0px 2px 0px 0px inset;
            color: rgb(200, 195, 188);
            display: inline-block;
            font-size: .85em;
            font-weight: 700;
            line-height: 1;
            padding: 2px 4px;
            white-space: nowrap;
    }
    </style>
    """)


    #####################################
    # sidebar
    #####################################
    # insert big logo for sidebar (st.logo() currently doesn't support img higher than 24 px..)
    st.html(
    """
    <style>
        [data-testid='stSidebarUserContent'] {
            background-image: url('./app/static/logo.png');
            background-position: 20px 20px;
            background-repeat: no-repeat;
            background-size: 80%;
            padding-top: 200px;
            margin-top: -60px;
       }
    </style>
    """)
    
    
    # reduce margin for st.divider() in sidebar
    # (--> compress menu length)
    st.html(
    """
    <style>
        [data-testid='stSidebarUserContent'] hr {
            margin: auto;
       }
    </style>
    """)
    
    
    # add left margin to st.header() in sidebar
    # (--> user-type-display is more centered)
    st.html(
    """
    <style>
        [data-testid='stSidebarUserContent'] h1 {
            margin-left: 20px;
       }
    </style>
    """)
    
    
    # reduce bottom margin for st.subheader() in sidebar
    # (--> "Logged in as" \n "Name" is closer together)
    st.html(
    """
    <style>
        [data-testid='stSidebarUserContent'] h3 {
            margin-bottom: -15px;
       }
    </style>
    """)
    
    
    #####################################
    # make top and bottom padding smaller
    #####################################
    st.html(
    """
    <style>
    .css-z5fcl4 {
        padding: 1rem 2rem 1rem 5rem;
        width: 99%;
    }
    </style>
    """)

    
    #####################################
    # hyperlink underline
    #####################################
    st.html(
    """
    <style>
    a, a:visited, a:hover, a:active {
        text-decoration: none;
    }
    </style>
    """)

    
    #####################################
    # login & clear data button
    #####################################
    st.html(
    """
    <style>
    .css-t6zrir {
        line-height: 2.2;
    }
    </style>
    """)

    
    ######################################
    # move toast from bottom right to top
    # & make it bigger
    ######################################
    st.html(
    """
    <style>
        div[data-testid=stToastContainer] {
                padding: 50px 10px 10px 10px;
                align-items: end;
                position: sticky; 
            }
           
            div[data-testid=stToast] {
                padding: 15px 25px 15px 25px;
                width: 20%;
            }
             
            [data-testid=stToastContainer] [data-testid=stMarkdownContainer] > p {
                font-size: 1.1rem;
            }
    </style>
    """)

    ######################################
    # make material symbols bigger
    ######################################
    st.html(
        """
        <style>
            [data-testid=stToastDynamicIcon], [data-testid=stIconMaterial], [data-testid=stAlertDynamicIcon]  {
                    font-size: 1.5rem;
                    margin-left: -2.5px;
                }
        </style>
        """)
    

