import streamlit as st
import cv2
from pyzbar import pyzbar
import requests
import numpy as np
from typing import Dict, List, Optional, Union
import time
from geopy.geocoders import Nominatim
import json
from datetime import datetime

class StoreFinder:
    """Handles finding nearby healthy food stores"""
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.geolocator = Nominatim(user_agent="healthy_food_finder")
    
    def get_current_location(self) -> tuple[float, float]:
        """Get current location using IP-based geolocation"""
        try:
            response = requests.get('https://ipapi.co/json/')
            data = response.json()
            return (data['latitude'], data['longitude'])
        except Exception as e:
            st.error(f"Error getting location: {str(e)}")
            return None

    def search_healthy_stores(self, 
                            latitude: float, 
                            longitude: float, 
                            radius: int = 1500,
                            food_preference: str = None) -> List[Dict]:
        """Search for healthy food stores near the specified location"""
        search_terms = [
            "health food store",
            "organic grocery",
            "farmers market",
            "whole foods",
            "natural food store"
        ]
        
        if food_preference:
            search_terms.append(food_preference)
            
        all_results = []
        
        for term in search_terms:
            url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            params = {
                "location": f"{latitude},{longitude}",
                "radius": radius,
                "keyword": term,
                "type": "store",
                "key": self.api_key
            }
            
            try:
                response = requests.get(url, params=params)
                data = response.json()
                
                if data.get("status") == "OK":
                    for place in data["results"]:
                        store_info = {
                            "name": place["name"],
                            "address": place.get("vicinity", "Address not available"),
                            "rating": place.get("rating", "No rating"),
                            "total_ratings": place.get("user_ratings_total", 0),
                            "open_now": place.get("opening_hours", {}).get("open_now", "Unknown"),
                            "location": {
                                "lat": place["geometry"]["location"]["lat"],
                                "lng": place["geometry"]["location"]["lng"]
                            }
                        }
                        
                        if store_info not in all_results:
                            all_results.append(store_info)
                            
            except Exception as e:
                st.error(f"Error searching for {term}: {str(e)}")
                
        return all_results

class HealthyFoodScanner:
    def __init__(self, google_api_key: str):
        self.api_url = "https://world.openfoodfacts.org/api/v0/product/"
        self.search_url = "https://world.openfoodfacts.org/cgi/search.pl"
        self.store_finder = StoreFinder(google_api_key)
        
        # Rest of the existing initialization code remains the same
        self.nutrition_facts_order = [
            ('energy-kcal_100g', 'Calories', 'kcal'),
            ('fat_100g', 'Total Fat', 'g'),
            ('saturated-fat_100g', '  Saturated Fat', 'g'),
            ('trans-fat_100g', '  Trans Fat', 'g'),
            ('cholesterol_100g', 'Cholesterol', 'mg'),
            ('sodium_100g', 'Sodium', 'mg'),
            ('carbohydrates_100g', 'Total Carbohydrates', 'g'),
            ('fiber_100g', '  Dietary Fiber', 'g'),
            ('sugars_100g', '  Sugars', 'g'),
            ('proteins_100g', 'Protein', 'g'),
            ('vitamin-d_100g', 'Vitamin D', 'µg'),
            ('calcium_100g', 'Calcium', 'mg'),
            ('iron_100g', 'Iron', 'mg'),
            ('potassium_100g', 'Potassium', 'mg')
        ]

    # All existing methods remain the same...
    # (format_number, process_frame, get_product_info, find_healthier_alternatives,
    # is_healthier_option, calculate_health_score)

    def find_nearby_healthy_stores(self, food_preference: Optional[str] = None) -> List[Dict]:
        """Find nearby stores that might have healthier options"""
        location = self.store_finder.get_current_location()
        if location:
            return self.store_finder.search_healthy_stores(
                latitude=location[0],
                longitude=location[1],
                food_preference=food_preference
            )
        return []

def main():
    st.set_page_config(page_title="Healthy Food Scanner", page_icon="🥗", layout="wide")
    
    # Add Google Places API key to Streamlit secrets or environment variables
    GOOGLE_API_KEY = st.secrets.get("google_places_api_key", "YOUR_API_KEY")
    
    st.title("🥗 Eatelligence")
    st.write("Scan a product barcode to get health information and find healthier alternatives!")

    scanner = HealthyFoodScanner(GOOGLE_API_KEY)

    # Initialize session state
    if 'barcode_detected' not in st.session_state:
        st.session_state.barcode_detected = False
    if 'product_info' not in st.session_state:
        st.session_state.product_info = None
    if 'show_stores' not in st.session_state:
        st.session_state.show_stores = False

    # Create tabs for different features
    scan_tab, stores_tab = st.tabs(["Scan Product", "Find Healthy Stores"])
    
    with scan_tab:
        # Original scanning functionality
        camera_col, info_col = st.columns([1, 1])
        
        with camera_col:
            st.write("### Scan Barcode")
            camera_input = st.camera_input("Point camera at barcode", key="camera")
            
            if camera_input is None and st.session_state.get('barcode_detected', False):
                st.session_state.barcode_detected = False
                st.session_state.product_info = None
                st.rerun()
            
            if camera_input is not None:
                image = cv2.imdecode(np.frombuffer(camera_input.getvalue(), np.uint8), cv2.IMREAD_COLOR)
                barcode = scanner.process_frame(image)
                
                if barcode:
                    st.session_state.barcode_detected = True
                    with st.spinner('Getting product information...'):
                        product_info = scanner.get_product_info(barcode)
                        if product_info:
                            st.session_state.product_info = product_info
                        else:
                            st.error("Product not found in database")
                else:
                    st.warning("No barcode detected. Please try again.")

        with info_col:
            if st.session_state.product_info:
                product_info = st.session_state.product_info
                health_score = scanner.calculate_health_score(product_info)
                
                st.write("### Product Information")
                st.write(f"**Product:** {product_info.get('product_name', 'Unknown')}")
                st.write(f"**Brand:** {product_info.get('brands', 'Unknown Brand')}")
                
                score_color = 'red' if health_score < 50 else 'orange' if health_score < 70 else 'green'
                st.markdown(f"**Health Score:** <span style='color:{score_color}'>{scanner.format_number(health_score)}/100</span>", unsafe_allow_html=True)
                
                if health_score < 70:
                    st.write("### 🥬 Healthier Alternatives")
                    alternatives = scanner.find_healthier_alternatives(product_info, health_score)
                    
                    if alternatives:
                        for i, alt in enumerate(alternatives, 1):
                            with st.expander(f"{i}. {alt['name']} by {alt['brand']} (Score: {scanner.format_number(alt['health_score'])}/100)"):
                                st.write(f"**Serving Size:** {alt['serving_size']}")
                                
                                st.write("**Nutrition Facts:**")
                                nutrients = alt['nutriments']
                                for nutrient_key, label, unit in scanner.nutrition_facts_order:
                                    if nutrient_key in nutrients:
                                        value = nutrients[nutrient_key]
                                        if unit == 'mg' and nutrient_key.endswith('_100g'):
                                            value = float(value) * 1000
                                        formatted_value = scanner.format_number(value)
                                        st.write(f"- {label}: {formatted_value}{unit}")
                        
                        # Add button to find stores with healthier alternatives
                        if st.button("Find stores with healthier options"):
                            st.session_state.show_stores = True
                            st.experimental_rerun()
                    else:
                        st.info("No healthier alternatives found in our database.")
    
    with stores_tab:
        st.write("### Find Healthy Food Stores Nearby")
        preference = st.text_input("Enter any specific food preference (e.g., organic, vegan) or leave blank:")
        
        if st.button("Search Nearby Stores"):
            with st.spinner("Finding stores near you..."):
                stores = scanner.find_nearby_healthy_stores(preference)
                
                if stores:
                    for store in stores:
                        with st.expander(f"📍 {store['name']} ({store['rating']} ⭐)"):
                            st.write(f"**Address:** {store['address']}")
                            st.write(f"**Rating:** {store['rating']} ({store['total_ratings']} reviews)")
                            st.write(f"**Open now:** {'Yes' if store['open_now'] else 'No'}")
                            
                            # Add map using store's coordinates
                            if store['location']:
                                map_url = f"https://www.google.com/maps/search/?api=1&query={store['location']['lat']},{store['location']['lng']}"
                                st.markdown(f"[Open in Google Maps]({map_url})")
                else:
                    st.warning("No stores found in your area. Try expanding the search radius or changing preferences.")

if __name__ == "__main__":
    main()