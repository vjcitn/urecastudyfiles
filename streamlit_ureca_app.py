#to run: streamlit run streamlit_ureca_app.py 
import streamlit as st
import pandas as pd
from frictionless import Resource, Dialect, formats
import sqlite3
import json

st.set_page_config(
    page_title="SDY1644 (URECA) Study Files",
    page_icon="🫁",
    layout="wide",
    initial_sidebar_state="expanded",
)


study_file_df = pd.read_csv("study_file_df.csv")
study_file_df_ureca = study_file_df[study_file_df["studyAccession"] == "SDY1644"]

CACHE = "metadata_cache.db"

connection_cache = sqlite3.connect(CACHE)
cursor_cache = connection_cache.cursor()
filename_list = study_file_df_ureca["fileName"].to_list()
res = connection_cache.execute('SELECT * FROM metadata_file_details WHERE file_name IN ({})'.format(', '.join(['?'] * len(filename_list))), [*filename_list])
fetched = res.fetchall()
cache_df = pd.DataFrame(fetched, columns = ["file_name", "generated_md5", "metadata"])

study_file_df_ureca_with_metadata = pd.merge(left = study_file_df_ureca, right = cache_df, left_on = "fileName", right_on = "file_name")

study_file_df_ureca_data_dictionaries = study_file_df_ureca[study_file_df_ureca["studyFileType"] == "Data Dictionary"]
data_dictionaries_list = study_file_df_ureca_data_dictionaries[study_file_df_ureca_data_dictionaries["fileName"].str.endswith("_dictionary.txt")]["fileName"].to_list()

file_and_corresponding_dictionary_dict = {}

for data_dictionary in data_dictionaries_list:
    corresponding_file = data_dictionary.replace("_dictionary", "")

    if study_file_df_ureca[study_file_df_ureca["fileName"] == corresponding_file].empty:
        print("no corresponding file found")
    else:
        file_and_corresponding_dictionary_dict[corresponding_file] = data_dictionary

st.header("SDY1644 (URECA) Study Files", divider=True)
st.dataframe(study_file_df_ureca[["fileName", "studyFileType", "description"]], hide_index=True, use_container_width=False)
st.divider()

st.header("File Details", divider=True)
selected_file_name = st.selectbox(
   "Which file would you like to see?",
   study_file_df_ureca["fileName"],
   index=None,
   placeholder="Select a file...",
)

st.write("You selected: **{}**".format(selected_file_name))
st.divider()

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
            st.dataframe(extracted_data, hide_index=True, use_container_width=True)

    elif selected_file_name.lower().endswith(".txt"):
        
        with Resource(base_path + selected_file_name, format='tsv', dialect = Dialect(skip_blank_rows=True)) as resource:
        
            extracted_data = pd.DataFrame(resource.read_rows())
            st.dataframe(extracted_data, hide_index=True, use_container_width=True)

    elif (selected_file_name.lower().endswith(".xlsx") or selected_file_name.lower().endswith(".xlsm") or selected_file_name.lower().endswith(".xls")):

        tabs_list = st.tabs(selected_file_metadata_json["sheet_names"])
        
        for index, tab in enumerate(tabs_list):

            with tab:

                sheet = selected_file_metadata_json["sheet_names"][index]

                with Resource(base_path + selected_file_name, control = formats.ExcelControl(sheet=sheet), dialect = Dialect(skip_blank_rows=True)) as resource:

                    extracted_data = pd.DataFrame(resource.read_rows())
                    st.dataframe(extracted_data, hide_index=True, use_container_width=True)

            
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
