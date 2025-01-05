import streamlit as st
import cv2
from pyzbar import pyzbar
import requests
import numpy as np
from typing import Dict, List, Optional, Union
import time

class HealthyFoodScanner:
    def __init__(self):
        self.api_url = "https://world.openfoodfacts.org/api/v0/product/"
        self.search_url = "https://world.openfoodfacts.org/cgi/search.pl"
        
        # Standard US nutrition facts order and units
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
    
    @staticmethod
    def format_number(value: Union[float, int, str]) -> str:
        """Format number to 2 decimal places"""
        try:
            return f"{float(value):.2f}"
        except (ValueError, TypeError):
            return str(value)

    def process_frame(self, frame) -> Optional[str]:
        """Process a single frame to detect barcodes"""
        if frame is not None:
            # Convert frame to grayscale for better barcode detection
            barcodes = pyzbar.decode(frame)
            
            for barcode in barcodes:
                barcode_data = barcode.data.decode("utf-8")
                return barcode_data
        return None

    def get_product_info(self, barcode: str) -> Optional[Dict]:
        """Fetch product information"""
        try:
            response = requests.get(f"{self.api_url}{barcode}.json")
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 1:
                    return data['product']
            return None
        except Exception as e:
            st.error(f"Error fetching product info: {e}")
            return None

    def find_healthier_alternatives(self, product_info: Dict, health_score: float) -> List[Dict]:
        """Find healthier alternatives from US market"""
        categories = product_info.get('categories_tags', [])
        main_category = next((cat for cat in categories if cat), 'unknown')
        current_nutrients = product_info.get('nutriments', {})
        
        params = {
            'action': 'process',
            'tagtype_0': 'categories',
            'tag_contains_0': 'contains',
            'tag_0': main_category,
            'tagtype_1': 'countries',
            'tag_contains_1': 'contains',
            'tag_1': 'united-states',
            'sort_by': 'nutrition_grades',
            'page_size': 100,
            'json': 1
        }
        
        alternatives = []
        try:
            with st.spinner('Searching for healthier alternatives...'):
                response = requests.get(self.search_url, params=params)
                if response.status_code == 200:
                    products = response.json().get('products', [])
                    
                    for product in products:
                        if product.get('code') == product_info.get('code'):
                            continue
                            
                        alt_score = self.calculate_health_score(product)
                        alt_nutrients = product.get('nutriments', {})
                        
                        countries = product.get('countries_tags', [])
                        if 'en:united-states' not in countries:
                            continue

                        if alt_score > health_score:
                            if self.is_healthier_option(current_nutrients, alt_nutrients):
                                alternatives.append({
                                    'name': product.get('product_name', 'Unknown'),
                                    'brand': product.get('brands', 'Unknown Brand'),
                                    'health_score': alt_score,
                                    'nutriments': alt_nutrients,
                                    'serving_size': product.get('serving_size', 'Not specified')
                                })
                    
                    alternatives.sort(key=lambda x: x['health_score'], reverse=True)
                    unique_alts = []
                    seen = set()
                    
                    for alt in alternatives:
                        if alt['name'] not in seen:
                            seen.add(alt['name'])
                            unique_alts.append(alt)
                            if len(unique_alts) >= 3:
                                break
                    
                    return unique_alts
                    
        except Exception as e:
            st.error(f"Error finding alternatives: {e}")
            return []

    def is_healthier_option(self, current_nutrients: Dict, alt_nutrients: Dict) -> bool:
        """Compare nutritional profiles"""
        better_count = 0
        total_comparisons = 0
        
        comparisons = {
            'sugars_100g': '<',
            'fat_100g': '<',
            'saturated-fat_100g': '<',
            'sodium_100g': '<',
            'proteins_100g': '>',
            'fiber_100g': '>'
        }
        
        for nutrient, comparison in comparisons.items():
            if nutrient in current_nutrients and nutrient in alt_nutrients:
                current_val = float(current_nutrients[nutrient] or 0)
                alt_val = float(alt_nutrients[nutrient] or 0)
                
                if comparison == '<' and alt_val < current_val:
                    better_count += 1
                elif comparison == '>' and alt_val > current_val:
                    better_count += 1
                total_comparisons += 1
        
        return total_comparisons > 0 and (better_count / total_comparisons) >= 0.6

    def calculate_health_score(self, product_info: Dict) -> float:
        """Calculate health score (1-100)"""
        score = 50.0
        nutrients = product_info.get('nutriments', {})
        
        negative_factors = {
            'sugars_100g': -5,
            'saturated-fat_100g': -5,
            'sodium_100g': -4,
            'fat_100g': -3
        }
        
        positive_factors = {
            'proteins_100g': 4,
            'fiber_100g': 4,
            'vitamin-d_100g': 2,
            'calcium_100g': 2,
            'iron_100g': 2,
            'potassium_100g': 2
        }
        
        for nutrient, impact in negative_factors.items():
            value = nutrients.get(nutrient, 0)
            score += impact * min(float(value), 10)
            
        for nutrient, impact in positive_factors.items():
            value = nutrients.get(nutrient, 0)
            score += impact * min(float(value), 10)
            
        return max(1.0, min(100.0, score))

def main():
    st.set_page_config(page_title="Healthy Food Scanner", page_icon="🥗", layout="wide")
    
    st.title("🥗 Healthy Food Scanner")
    st.write("Scan a product barcode to get health information and find healthier alternatives!")

    scanner = HealthyFoodScanner()

    # Initialize session state
    if 'barcode_detected' not in st.session_state:
        st.session_state.barcode_detected = False
    if 'product_info' not in st.session_state:
        st.session_state.product_info = None

    # Camera input
    camera_col, info_col = st.columns([1, 1])
    
    with camera_col:
        st.write("### 📸 Scan Barcode")
        camera_input = st.camera_input("Point camera at barcode", key="camera")
        
        if camera_input is not None:
            # Convert the image to numpy array
            image = cv2.imdecode(np.frombuffer(camera_input.getvalue(), np.uint8), cv2.IMREAD_COLOR)
            
            # Process the frame
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
            
            st.write("### 📊 Product Information")
            st.write(f"**Product:** {product_info.get('product_name', 'Unknown')}")
            st.write(f"**Brand:** {product_info.get('brands', 'Unknown Brand')}")
            
            # Display health score with color
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
                else:
                    st.info("No healthier alternatives found in our database.")

    # Reset button
    if st.session_state.barcode_detected:
        if st.button("Scan Another Product"):
            st.session_state.barcode_detected = False
            st.session_state.product_info = None
            st.experimental_rerun()

if __name__ == "__main__":
    main()