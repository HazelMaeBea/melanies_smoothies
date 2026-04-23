import streamlit as st
import requests
import pandas as pd
from urllib.parse import quote
from snowflake.snowpark.functions import col


def build_lookup_candidates(search_on, fruit_name):
    """Build a small ordered list of lookup values to try against Fruityvice."""
    candidates = []
    for value in [search_on, fruit_name]:
        if value is None:
            continue
        cleaned = str(value).strip()
        if cleaned and cleaned not in candidates:
            candidates.append(cleaned)

        # Fruityvice often expects the core fruit name without alias in parentheses.
        without_alias = cleaned.split(" (")[0].strip()
        if without_alias and without_alias not in candidates:
            candidates.append(without_alias)

    return candidates


st.title("Customize Your Smoothie :cup_with_straw:")
st.write("""Choose the fruits you want in your custom smoothie!""")

name_on_order = st.text_input("Name on Smoothie")
st.write("The name on your smoothie will be: ", name_on_order)

try:
    # Use st.connection() as per Streamlit documentation
    # This handles both private_key_file (local) and private_key (cloud) automatically
    conn = st.connection("snowflake")
    session = conn.session()

    # Retrieve fruit options from Snowflake
    my_dataframe = session.table("smoothies.public.fruit_options").select(
        col("FRUIT_NAME"), col('SEARCH_ON'))  # .collect()

    # my_dataframe to pandas
    pd_df = my_dataframe.to_pandas()
    # st.dataframe(pd_df)
    # st.stop()

    # Multi-select for choosing ingredients
    ingredients_list = st.multiselect(
        "Choose up to 5 ingredients:",
        pd_df["FRUIT_NAME"].tolist(),
        max_selections=5,
    )

    # Process ingredients selection
    if ingredients_list:
        # Join selected ingredients into a single string
        ingredients_string = ' '.join(ingredients_list)

        for fruit_chosen in ingredients_list:
            try:
                raw_search_on = pd_df.loc[pd_df['FRUIT_NAME']
                                          == fruit_chosen, 'SEARCH_ON'].iloc[0]
                search_on = raw_search_on if pd.notna(
                    raw_search_on) else fruit_chosen
                st.write('The search value for ',
                         fruit_chosen, ' is ', search_on, '.')

                # Make API request to get details about each fruit
                fruityvice_response = None
                last_request_error = None
                for lookup_value in build_lookup_candidates(search_on, fruit_chosen):
                    request_url = "https://fruityvice.com/api/fruit/" + \
                        quote(lookup_value, safe="")
                    try:
                        response = requests.get(request_url, timeout=10)
                        response.raise_for_status()
                        fruityvice_response = response
                        break
                    except requests.exceptions.RequestException as request_error:
                        last_request_error = request_error

                if fruityvice_response is None and last_request_error is not None:
                    raise last_request_error
                if fruityvice_response is None:
                    raise ValueError(
                        f"No Fruityvice response received for {fruit_chosen}")

                if fruityvice_response.status_code == 200:
                    fv_df = st.dataframe(
                        data=fruityvice_response.json(), use_container_width=True)
                else:
                    st.warning(f"Failed to fetch details for {fruit_chosen}")

            except requests.exceptions.RequestException as e:
                st.error(
                    f"Failed to fetch details for {fruit_chosen}: {str(e)}")

        # SQL statement to insert order into database
        my_insert_stmt = """INSERT INTO smoothies.public.orders(ingredients, name_on_order)
                VALUES ('{}', '{}')""".format(ingredients_string, name_on_order)

        # Button to submit order
        time_to_insert = st.button('Submit Order')
        if time_to_insert:
            try:
                # Execute SQL insert statement
                session.sql(my_insert_stmt).collect()
                st.success('Your Smoothie is ordered, ' +
                           name_on_order + '!', icon="✅")
            except Exception as e:
                st.error(f"Failed to submit order: {str(e)}")

except Exception as ex:
    st.error(f"An error occurred: {str(ex)}")

# # Display a link
# st.write("https://github.com/appuv")
