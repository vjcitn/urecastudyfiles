#to run: streamlit run streamlit_ureca_app.py 
import streamlit as st
import pandas as pd
from frictionless import Resource, Dialect, formats
import sqlite3
import json

from pandas.api.types import (
    is_categorical_dtype,
    is_datetime64_any_dtype,
    is_numeric_dtype,
    is_object_dtype,
)
import warnings
from random import choice
from string import digits

import hmac

def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if hmac.compare_digest(st.session_state["password"], st.secrets["password"]):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store the password.
        else:
            st.session_state["password_correct"] = False

    # Return True if the password is validated.
    if st.session_state.get("password_correct", False):
        return True

    # Show input for password.
    st.text_input(
        "Password", type="password", on_change=password_entered, key="password"
    )
    if "password_correct" in st.session_state:
        st.error("😕 Password incorrect")
    return False

if not check_password():
    st.stop()  # Do not continue if check_password is not True.


def dataframe_explorer(df: pd.DataFrame, case: bool = True) -> pd.DataFrame:
    """
    Adds a UI on top of a dataframe to let viewers filter columns

    Args:
        df (pd.DataFrame): Original dataframe
        case (bool, optional): If True, text inputs will be case sensitive. Defaults to True.

    Returns:
        pd.DataFrame: Filtered dataframe
    """

    if df.empty: #this prevents key collisions when multiple empty dataframes exist, since they won't have unique hash values
        random_key_base = ''.join(choice(digits) for i in range(12))
    else:
        random_key_base = pd.util.hash_pandas_object(df)

    modify = st.checkbox("Add filters", key=f"{random_key_base}_checkbox")

    if not modify:
        return df

    df = df.copy()

    # Try to convert datetimes into standard format (datetime, no timezone)
    for col in df.columns:
        if is_object_dtype(df[col]):
            try:
                with warnings.catch_warnings(): #suppresses: UserWarning: Could not infer format, so each element will be parsed individually, falling back to `dateutil`. To ensure parsing is consistent and as-expected, please specify a format.
                    warnings.simplefilter("ignore")
                    df[col] = pd.to_datetime(df[col])
            except Exception:
                pass

        if is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.tz_localize(None)

    modification_container = st.container()

    with modification_container:
        to_filter_columns = st.multiselect(
            "Filter dataframe on",
            df.columns,
            key=f"{random_key_base}_multiselect",
        )
        filters: Dict[str, Any] = dict()
        for column in to_filter_columns:
            left, right = st.columns((1, 20))
            # Treat columns with < 10 unique values as categorical
            # if is_categorical_dtype(df[column]) or df[column].nunique() < 10: #is_categorical_dtype() is deprecated
            if isinstance(df[column].dtype, pd.CategoricalDtype) or df[column].nunique() < 10:
                left.write("↳")
                if df[column].notnull().all():
                    df_column = df[column] #don't attempt to fillna if there are none, because this leads to an error with categorial columns
                else:
                    df_column = df[column].fillna("None") #must fill missing values, because multiselect widget errors out with nan values present

                filters[column] = right.multiselect(
                    f"Values for {column}",
                    df_column.unique(), 
                    default=list(df_column.unique()),
                    key=f"{random_key_base}_{column}",
                )
                df = df[df_column.isin(filters[column])]
            elif is_numeric_dtype(df[column]):
                left.write("↳")
                _min = float(df[column].min())
                _max = float(df[column].max())
                step = (_max - _min) / 100
                filters[column] = right.slider(
                    f"Values for {column}",
                    _min,
                    _max,
                    (_min, _max),
                    step=step,
                    key=f"{random_key_base}_{column}",
                )
                df = df[df[column].between(*filters[column])]
            elif is_datetime64_any_dtype(df[column]):
                left.write("↳")
                filters[column] = right.date_input(
                    f"Values for {column}",
                    value=(
                        df[column].min(),
                        df[column].max(),
                    ),
                    key=f"{random_key_base}_{column}",
                )
                if len(filters[column]) == 2:
                    filters[column] = tuple(map(pd.to_datetime, filters[column]))
                    start_date, end_date = filters[column]
                    df = df.loc[df[column].between(start_date, end_date)]
            else:
                left.write("↳")
                filters[column] = right.text_input(
                    f"Search in {column}",
                    key=f"{random_key_base}_{column}",
                )
                if filters[column]:
                    df = df[df[column].str.contains(filters[column], case=case, na = False)]

    return df

st.set_page_config(
    page_title="SDY1644 (URECA) Study Files",
    page_icon="🫁",
    layout="wide",
    initial_sidebar_state="expanded",
)

#load study files df
study_file_df = pd.read_csv("study_file_df.csv")
study_file_df_ureca = study_file_df[study_file_df["studyAccession"] == "SDY1644"]

#load metadata file details
CACHE = "metadata_cache.db"
connection_cache = sqlite3.connect(CACHE)
cursor_cache = connection_cache.cursor()
filename_list = study_file_df_ureca["fileName"].to_list()
res = connection_cache.execute('SELECT * FROM metadata_file_details WHERE file_name IN ({})'.format(', '.join(['?'] * len(filename_list))), [*filename_list])
fetched = res.fetchall()
cache_df = pd.DataFrame(fetched, columns = ["file_name", "generated_md5", "metadata"])

study_file_df_ureca_with_metadata = pd.merge(left = study_file_df_ureca, right = cache_df, left_on = "fileName", right_on = "file_name")

#load AI generated file details
CACHE_AI = "ai_gen_cache.db"
connection_cache_ai = sqlite3.connect(CACHE_AI)
cursor_cache_ai = connection_cache_ai.cursor()
res_ai = connection_cache_ai.execute('SELECT * FROM ai_generated_file_details WHERE file_name IN ({})'.format(', '.join(['?'] * len(filename_list))), [*filename_list])
fetched_ai = res_ai.fetchall()
cache_ai_df = pd.DataFrame(fetched_ai, columns = ["file_name", "generated_md5", "ai_generated_keywords", "ai_generated_summary", "cost"])

study_file_df_ureca_with_ai_generated = pd.merge(left = study_file_df_ureca, right = cache_ai_df, left_on = "fileName", right_on = "file_name")

#create one big df with both metadata and AI generated file details
study_file_df_ureca_with_all_file_details = pd.merge(left = study_file_df_ureca, right = cache_ai_df, left_on = "fileName", right_on = "file_name", how = "left")
study_file_df_ureca_with_all_file_details = pd.merge(left = study_file_df_ureca_with_all_file_details, right = cache_df, left_on = "file_name", right_on = "file_name", how = "left")
categorical_cols = ["studyFileType"]
study_file_df_ureca_with_all_file_details[categorical_cols] = study_file_df_ureca_with_all_file_details[categorical_cols].astype('category')

study_file_df_ureca_with_all_file_details["metadata_available"] = [False if pd.isnull(row) else "result" not in json.loads(row) for row in study_file_df_ureca_with_all_file_details["metadata"]] 

#create file and corresponding data dictionary mapping
study_file_df_ureca_data_dictionaries = study_file_df_ureca[study_file_df_ureca["studyFileType"] == "Data Dictionary"]
data_dictionaries_list = study_file_df_ureca_data_dictionaries[study_file_df_ureca_data_dictionaries["fileName"].str.endswith("_dictionary.txt")]["fileName"].to_list()

file_and_corresponding_dictionary_dict = {}

for data_dictionary in data_dictionaries_list:
    corresponding_file = data_dictionary.replace("_dictionary", "")

    if study_file_df_ureca[study_file_df_ureca["fileName"] == corresponding_file].empty:
        print("no corresponding file found")
    else:
        file_and_corresponding_dictionary_dict[corresponding_file] = data_dictionary

#----------
#display info on page
#----------
st.header("SDY1644 (URECA) Study Files", divider=True)
st.dataframe(study_file_df_ureca[["fileName", "studyFileType", "description"]], hide_index=True, use_container_width=False)
st.divider()


st.subheader('Search and Filter Files')
filtered_df = dataframe_explorer(study_file_df_ureca_with_all_file_details[["fileName", "studyFileType", "description", "ai_generated_keywords", "ai_generated_summary", "metadata", "metadata_available"]], case=False)
st.write(len(filtered_df), "matching files found")
st.dataframe(filtered_df, hide_index=True, use_container_width=True)
st.divider()

st.header("File Details", divider=True)
selected_file_name = st.selectbox(
   "Which file would you like to see?",
   study_file_df_ureca["fileName"],
   index=None,
   placeholder="Select a file...",
)

st.write("You selected: **{}**".format(selected_file_name))
if selected_file_name is not None:
    st.write("")
    st.write("**Study File Type:** {}".format(study_file_df_ureca[study_file_df_ureca["fileName"] == selected_file_name]["studyFileType"].values[0]))
    st.write("**Description:** {}".format(study_file_df_ureca[study_file_df_ureca["fileName"] == selected_file_name]["description"].values[0]))
st.divider()


#get AI generated file details of selected file, if it exists
selected_file_ai_generated_row_df = study_file_df_ureca_with_ai_generated[study_file_df_ureca_with_ai_generated["fileName"] == selected_file_name]

st.subheader('AI Generated Summary and Keywords')
if selected_file_ai_generated_row_df.empty: #this means it doesn't exist in cache
    st.write("No summary/keywords found for this file")

else: #this means it does exist in cache
    st.write("**Summary:** {}".format(selected_file_ai_generated_row_df["ai_generated_summary"].values[0]))
    st.write("**Keywords:** {}".format(selected_file_ai_generated_row_df["ai_generated_keywords"].values[0]))


#get metadata of selected file, if it exists
selected_file_metadata = study_file_df_ureca_with_metadata[study_file_df_ureca_with_metadata["fileName"] == selected_file_name]["metadata"]

st.subheader('File Metadata')
if selected_file_metadata.empty: #this means it doesn't exist in cache
    st.write("No metadata found for this file")

else: #this means it does exist in cache
    selected_file_metadata_json = json.loads(selected_file_metadata.values[0])

    if "result" in selected_file_metadata_json:
        st.write("No valid metadata found for this file")
    else:
        with st.container(height = 400): #putting this inside a container with fixed height inserts scrollbars
            st.json(selected_file_metadata_json, expanded = True)


st.subheader('Data Preview')
base_path = "example_files/SDY1644/StudyFiles/"

if (selected_file_metadata.empty) or ("result" in selected_file_metadata_json):
    st.write("No preview available for this file")
else:

    if (selected_file_name.lower().endswith(".csv") or selected_file_name.lower().endswith(".tsv")):
    
        with Resource(base_path + selected_file_name, dialect = Dialect(skip_blank_rows=True)) as resource:
                
            extracted_data = pd.DataFrame(resource.read_rows())
            extracted_data_filtered = dataframe_explorer(extracted_data, case=False)
            st.write(len(extracted_data_filtered), "matching rows found")
            st.dataframe(extracted_data_filtered, hide_index=True, use_container_width=True)

    elif selected_file_name.lower().endswith(".txt"):
        
        with Resource(base_path + selected_file_name, format='tsv', dialect = Dialect(skip_blank_rows=True)) as resource:
        
            extracted_data = pd.DataFrame(resource.read_rows())
            extracted_data_filtered = dataframe_explorer(extracted_data, case=False)
            st.write(len(extracted_data_filtered), "matching rows found")
            st.dataframe(extracted_data_filtered, hide_index=True, use_container_width=True)

    elif (selected_file_name.lower().endswith(".xlsx") or selected_file_name.lower().endswith(".xlsm") or selected_file_name.lower().endswith(".xls")):

        tabs_list = st.tabs(selected_file_metadata_json["sheet_names"])
        
        for index, tab in enumerate(tabs_list):

            with tab:

                sheet = selected_file_metadata_json["sheet_names"][index]

                with Resource(base_path + selected_file_name, control = formats.ExcelControl(sheet=sheet), dialect = Dialect(skip_blank_rows=True)) as resource:

                    extracted_data = pd.DataFrame(resource.read_rows())
                    extracted_data_filtered = dataframe_explorer(extracted_data, case=False)
                    st.write(len(extracted_data_filtered), "matching rows found")
                    st.dataframe(extracted_data_filtered, hide_index=True, use_container_width=True)

            
#need to first check if selected file is data dict, corresponding file, or neither and only print relevent section for each of those 3
if selected_file_name in file_and_corresponding_dictionary_dict:
    st.subheader('Data Dictionary')
    corresponding_dictionary_file_name = file_and_corresponding_dictionary_dict[selected_file_name]
    st.write("This file has a data dictionary that describes it.  The data dictionary file is: **{}**".format(corresponding_dictionary_file_name))

    st.markdown('##### Data Dictionary Preview')
    with Resource(base_path + corresponding_dictionary_file_name, format='tsv', dialect = Dialect(skip_blank_rows=True)) as resource:
    
        extracted_data_dictionary = pd.DataFrame(resource.read_rows())
    
    st.dataframe(extracted_data_dictionary, hide_index=True, use_container_width=True)


elif selected_file_name in file_and_corresponding_dictionary_dict.values():
    st.subheader('Corresponding File')
    for corresponding_file_name, corresponding_dictionary_file_name in file_and_corresponding_dictionary_dict.items():
        if corresponding_dictionary_file_name == selected_file_name:
            st.write("This file is a data dictionary file.  The file it describes is: **{}**".format(corresponding_file_name))
            break

else:
    st.subheader('Additional Information')
    st.write("File is not part of a data dictionary / corresponding file pair")
