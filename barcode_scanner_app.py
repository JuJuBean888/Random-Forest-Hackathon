import cv2
from pyzbar import pyzbar
import requests
import time
from typing import Dict, List, Optional, Union

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

    def scan_barcode(self) -> Optional[str]:
        """Scan barcode with 30-second timeout"""
        cap = cv2.VideoCapture(0)
        start_time = time.time()
        timeout = 30

        while True:
            if time.time() - start_time > timeout:
                print("\nTimeout: No barcode scanned within 30 seconds")
                break

            ret, frame = cap.read()
            if not ret:
                print("Failed to grab frame")
                break

            barcodes = pyzbar.decode(frame)
            for barcode in barcodes:
                (x, y, w, h) = barcode.rect
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                
                barcode_data = barcode.data.decode("utf-8")
                cv2.putText(frame, barcode_data, (x, y - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                cap.release()
                cv2.destroyAllWindows()
                return barcode_data

            remaining = int(timeout - (time.time() - start_time))
            cv2.putText(frame, f"Time remaining: {remaining}s", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imshow("Barcode Scanner (Press q to quit)", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()
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
            print(f"Error fetching product info: {e}")
            return None

    def display_nutrition_facts(self, product_info: Dict):
        """Display nutrition facts in US format"""
        nutrients = product_info.get('nutriments', {})
        serving_size = product_info.get('serving_size', 'Not specified')
        
        print("\nNUTRITION FACTS")
        print("=" * 40)
        print(f"Serving Size: {serving_size}")
        print("-" * 40)
        
        # Display nutrients in standard US format
        for nutrient_key, label, unit in self.nutrition_facts_order:
            if nutrient_key in nutrients:
                value = nutrients[nutrient_key]
                if unit == 'mg' and nutrient_key.endswith('_100g'):
                    # Convert g to mg for relevant nutrients
                    value = float(value) * 1000
                formatted_value = self.format_number(value)
                print(f"{label}: {formatted_value}{unit}")

    def find_healthier_alternatives(self, product_info: Dict, health_score: float) -> List[Dict]:
        """Find healthier alternatives from US market"""
        categories = product_info.get('categories_tags', [])
        main_category = next((cat for cat in categories if cat), 'unknown')
        current_nutrients = product_info.get('nutriments', {})
        
        # Search parameters specifically for US products
        params = {
            'action': 'process',
            'tagtype_0': 'categories',
            'tag_contains_0': 'contains',
            'tag_0': main_category,
            'tagtype_1': 'countries',
            'tag_contains_1': 'contains',
            'tag_1': 'united-states',
            'sort_by': 'nutrition_grades',
            'page_size': 100,  # Increased to find more US products
            'json': 1
        }
        
        alternatives = []
        try:
            response = requests.get(self.search_url, params=params)
            if response.status_code == 200:
                products = response.json().get('products', [])
                
                for product in products:
                    if product.get('code') == product_info.get('code'):
                        continue
                        
                    alt_score = self.calculate_health_score(product)
                    alt_nutrients = product.get('nutriments', {})
                    
                    # Only include products available in the US
                    countries = product.get('countries_tags', [])
                    if 'en:united-states' not in countries:
                        continue

                    if alt_score > health_score:
                        if self.is_healthier_option(current_nutrients, alt_nutrients):
                            # Get US-specific store information
                            stores = product.get('stores', 'Not specified')
                            purchase_places = product.get('purchase_places', '')
                            
                            alternatives.append({
                                'name': product.get('product_name', 'Unknown'),
                                'brand': product.get('brands', 'Unknown Brand'),
                                'health_score': alt_score,
                                'nutriments': alt_nutrients,
                                'serving_size': product.get('serving_size', 'Not specified'),
                                'stores': stores,
                                'locations': purchase_places
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
            print(f"Error finding alternatives: {e}")
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
    scanner = HealthyFoodScanner()
    print("Please show a barcode to the camera (30-second timeout)...")
    
    barcode = scanner.scan_barcode()
    if barcode:
        print(f"\nBarcode detected: {barcode}")
        product_info = scanner.get_product_info(barcode)
        
        if product_info:
            health_score = scanner.calculate_health_score(product_info)
            
            print(f"\nProduct: {product_info.get('product_name', 'Unknown')}")
            print(f"Brand: {product_info.get('brands', 'Unknown Brand')}")
            print(f"Health Score: {scanner.format_number(health_score)}/100")
            
            scanner.display_nutrition_facts(product_info)
            
            if health_score < 70:
                print("\nHEALTHIER ALTERNATIVES")
                print("=" * 40)
                alternatives = scanner.find_healthier_alternatives(product_info, health_score)
                
                if alternatives:
                    for i, alt in enumerate(alternatives, 1):
                        print(f"\n{i}. {alt['name']} by {alt['brand']}")
                        print(f"   Health Score: {scanner.format_number(alt['health_score'])}/100")
                        print(f"   Serving Size: {alt['serving_size']}")
                        
                        print("\n   Nutrition Facts:")
                        print("   " + "=" * 30)
                        nutrients = alt['nutriments']
                        for nutrient_key, label, unit in scanner.nutrition_facts_order:
                            if nutrient_key in nutrients:
                                value = nutrients[nutrient_key]
                                if unit == 'mg' and nutrient_key.endswith('_100g'):
                                    value = float(value) * 1000
                                formatted_value = scanner.format_number(value)
                                print(f"   {label}: {formatted_value}{unit}")
                        # Display store information if available
                        if alt['stores'] != 'Not specified':
                            print(f"   Available at: {alt['stores']}")
                        if alt['locations']:
                            print(f"   Found in: {alt['locations']}")
                        print()
                else:
                    print("\nNo healthier alternatives found in our database.")
        else:
            print("Product not found in database")
    else:
        print("No barcode detected or scan timeout")

if __name__ == "__main__":
    main()