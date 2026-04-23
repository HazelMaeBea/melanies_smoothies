import streamlit as st
import requests
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from snowflake.snowpark import Session
from snowflake.snowpark.functions import col

st.title("Customize Your Smoothie :cup_with_straw:")
st.write("""Choose the fruits you want in your custom smoothie!""")

name_on_order = st.text_input("Name on Smoothie")
st.write("The name on your smoothie will be: ", name_on_order)

try:
    snowflake_cfg = dict(st.secrets["connections"]["snowflake"])

    # Use key text from secrets in cloud, and key files for local development.
    if "private_key" in snowflake_cfg and str(snowflake_cfg["private_key"]).strip():
        private_key_pem = str(snowflake_cfg.pop("private_key"))
    elif "private_key_file" in snowflake_cfg:
        key_path = Path(str(snowflake_cfg.pop("private_key_file")))
        if not key_path.is_absolute():
            key_path = (Path(__file__).resolve().parent / key_path).resolve()
        if not key_path.exists():
            raise FileNotFoundError(
                "Snowflake private key file was not found. "
                "For Streamlit Cloud, set [connections.snowflake].private_key in secrets. "
                f"Checked path: {key_path}"
            )
        private_key_pem = key_path.read_text(encoding="utf-8")
    else:
        raise ValueError(
            "Missing Snowflake private key. Provide either 'private_key' or 'private_key_file' "
            "under [connections.snowflake] in secrets."
        )

    passphrase = snowflake_cfg.pop("private_key_passphrase", None)
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode("utf-8"),
        password=passphrase.encode("utf-8") if passphrase else None,
    )
    snowflake_cfg["private_key"] = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    session = Session.builder.configs(snowflake_cfg).create()

    # Retrieve fruit options from Snowflake
    my_dataframe = session.table("smoothies.public.fruit_options").select(
        col("FRUIT_NAME")).collect()

    # Multi-select for choosing ingredients
    ingredients_list = st.multiselect(
        "Choose up to 5 ingredients:",
        [row["FRUIT_NAME"] for row in my_dataframe],
        max_selections=5,
    )

    # Process ingredients selection
    if ingredients_list:
        # Join selected ingredients into a single string
        ingredients_string = ' '.join(ingredients_list)
        for fruit_chosen in ingredients_list:
            try:
                # Make API request to get details about each fruit
                fruityvice_response = requests.get(
                    "https://fruityvice.com/api/fruit/" + fruit_chosen)
                # Raise an error for bad responses (4xx or 5xx)
                fruityvice_response.raise_for_status()

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
