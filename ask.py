import streamlit as st
from openai import OpenAI
import requests
import json

api_key = st.secrets["OPENAI_API_KEY"]
places_api = st.secrets["GOOGLE_API_KEY"]

# Function to dynamically extract location and intent using OpenAI GPT
def parse_user_input_with_llm(user_input):
    OpenAI.api_key = api_key

    # Prompt to extract intent and location
    prompt = f"""
Analyze the following user query and extract relevant information.
Identify the location and the intent of the query. The intent may involve searching for various types of places or services (e.g., schools, coffee shops, parks, restaurants, museums, etc.).
Your response should intelligently determine the type of place or service being requested, even if not explicitly stated.
Query: "{user_input}"
Provide the result in this JSON format:
{{
    "location": "<location>",
    "intent": "<intent>",
    "place_type": "<place_type>"
}}

If the location is not mentioned, indicate it as "unspecified" and suggest a default location based on the context.
"""

    # Call OpenAI API
    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant skilled in parsing user queries."},
            {"role": "user", "content": prompt},
        ]
    )

    # Parse the LLM's response
    result = response.choices[0].message.content  # Corrected access method
    try:
        parsed_result = json.loads(result)
        location = parsed_result.get("location", "").strip()
        place_type = (parsed_result.get("place_type") or "point_of_interest").strip()
        return location, place_type
    except json.JSONDecodeError:
        st.error("Error parsing LLM response.")
        return "", "point_of_interest"

# Function to fetch nearby places from Google Places API
def fetch_nearby_places(location, radius, place_type):
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": location,  # Latitude and Longitude (e.g., "47.6062,-122.3321")
        "radius": radius,  # Search radius in meters
        "type": place_type,  # Place type, e.g., "tourist_attraction"
        "key": places_api,
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

# Function to process the API response for the LLM
def prepare_data_for_llm(api_data):
    places = []
    for result in api_data.get("results", []):
        place = {
            "name": result.get("name"),
            "vicinity": result.get("vicinity"),
            "rating": result.get("rating"),
        }
        places.append(place)
    return places

# Function to generate concise descriptions using OpenAI GPT
def generate_concise_description(places, query):
    OpenAI.api_key = api_key

    # Prepare prompt
    #prompt = f"Using the following data, provide a concise response to the query: '{query}'\n"
    
    data = ""
    for place in places:
        data += f"- **{place['name']}**: Located at {place['vicinity']}, rated {place['rating']}/5.\n"


    prompt = f"""
Using the following data, please provide a concise and informative response to the user's query: '{query}'.

Here is the data you can refer to:
{data}

Please format your response as a list of key points or items, making it easy to read and understand. 
Humanize the information by using a conversational tone and highlighting relevant details that would be useful for the user.
{data} should not exceed 3 bullet points.
"""
    
    

    # Call OpenAI API
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ]
    )

    # Extract and return the LLM's response
    return response.choices[0].message.content  # Corrected access method

def geocode_location(location):
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": location,
        "key": places_api,
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    if data["results"]:
        lat_lng = data["results"][0]["geometry"]["location"]
        return lat_lng["lat"], lat_lng["lng"]
    else:
        st.error("Could not geocode the location.")
        return None, None
    
# Streamlit App
def main():
    st.title("AI-Powered Place Recommender")

    # Example queries for users to click
    example_queries = [
        "Tell me things to do in Portland Downtown",
        "Coffee spots around San Francisco",
        "Top tourist attractions in New York",
        "Restaurants near Los Angeles",
        "Parks in Chicago"
    ]

    # Display example queries as buttons
    st.sidebar.header("Example Queries")
    for query in example_queries:
        if st.sidebar.button(query):
            st.session_state.user_input = query  # Store the clicked query in session state
            st.rerun()  # Rerun the script to process the new input

    # User input
    user_input = st.text_input("Ask something:", placeholder="e.g., Tell me things to do around Seattle", 
                                value=st.session_state.get("user_input", ""))

    if user_input:
        with st.spinner("Analyzing query..."):
            location, place_type = parse_user_input_with_llm(user_input)

        if not location or location.lower() == "unspecified":
            st.error("Please specify a location in your query.")
            return

        # Geocode the location to get coordinates
        lat, lng = geocode_location(location)

        if lat is None or lng is None:
            st.error("Could not retrieve coordinates for the specified location.")
            return

        location_coords = f"{lat},{lng}"

        # Fetch data from Google Places API using the coordinates
        with st.spinner("Fetching nearby places..."):
            api_response = fetch_nearby_places(location_coords, 1500, place_type)

        # Process the data for the LLM
        places = prepare_data_for_llm(api_response)

        if not places:
            st.warning("No results found for the specified location and query.")
            return

        # Generate concise description using OpenAI
        with st.spinner("Generating response..."):
            concise_response = generate_concise_description(places, user_input)

        # Display the output
        st.success("Response:")
        st.write(concise_response)

if __name__ == "__main__":
    main()