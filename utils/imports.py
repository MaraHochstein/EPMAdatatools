#######################
# imports & config
#######################
# streamlit
import streamlit as st
from streamlit import session_state as sst

# api requests
from streamlit_oauth import OAuth2Component # oauth popup
import requests as requests # api requests
import urllib # parse url

# general
import datetime
import pandas as pd
import io
import re # regex search
import os
import copy # make deepcopy of var
import openpyxl # for xlsx processing

# images
from PIL import Image
import tifffile as tiff

# text styling
#from annotated_text import annotated_text # needs requirements: streamlit_extras
#from streamlit_extras.keyboard_text import key

# for mineral identification charts & calc
import numpy as np
import altair as alt # bar plot minerals
import plotly.graph_objects as go

# # #
import base64
import imagecodecs
from streamlit.components.v1 import html