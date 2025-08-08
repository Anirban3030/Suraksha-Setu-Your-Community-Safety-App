import streamlit as st
from streamlit_folium import st_folium
import folium
from datetime import datetime, timedelta, timezone
import pandas as pd
from io import StringIO
from streamlit_geolocation import streamlit_geolocation
import requests
import re
import firebase_admin
from firebase_admin import credentials, firestore
import os
import math
import json
import time


# adding deployed backend url 
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

# Initialize Streamlit app
st.set_page_config(page_title="🛡️ Suraksha Setu - Community Safety Reporting System",layout='wide', initial_sidebar_state='expanded')



# Add spacing at the top
st.markdown("""
<style>
.space {
   margin-top: 20px;
   margin-bottom: 20px;
}
</style>
<div class="space"></div>
""", unsafe_allow_html=True)
 # Clear any previous content
st.markdown("<h1 style='text-align: center;'>🛡️ Suraksha Setu - Community Safety Reporting System</h1>", unsafe_allow_html=True)
# Initialize Firebase (only if not already initialized)

if not firebase_admin._apps:
    try:
        firebase_creds = os.getenv("FIREBASE_CREDENTIALS")

        if firebase_creds:
            # ✅ For Render or any environment where credentials are passed via env var
            cred = credentials.Certificate(json.loads(firebase_creds))
            firebase_admin.initialize_app(cred)
            st.success("✅ Firebase initialized from environment variable.")
        else:
            # ✅ Fallback for local dev — check for local file
            service_key_paths = [
                "serviceAccountKey.json",
                "../serviceAccountKey.json",
                os.path.join("..", "serviceAccountKey.json"),
            ]

            service_key_path = None
            for path in service_key_paths:
                if os.path.exists(path):
                    service_key_path = path
                    break

            if service_key_path:
                cred = credentials.Certificate(service_key_path)
                firebase_admin.initialize_app(cred)
                st.success(f"✅ Firebase initialized from local file: {service_key_path}")
            else:
                st.error("❌ Firebase credentials not found (env or file).")
                st.stop()
    except Exception as e:
        st.error(f"❌ Firebase initialization error: {e}")
        st.stop()

# Initialize Firestore client
db = firestore.client()

@st.cache_data(ttl=30)  # Cache for 30 seconds to improve performance
def fetch_incidents_from_firebase():
    """Fetch all incidents directly from Firebase Firestore"""
    try:
        docs = db.collection("incident_reports").stream()
        incidents = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            incidents.append(data)
        return incidents
    except Exception as e:
        st.error(f"Error fetching incidents from Firebase: {e}")
        return []

def extract_coordinates_from_location(location_text):
    """Extract latitude and longitude from location text"""
    try:
        
        match = re.search(r'\((-?\d+\.?\d*),\s*(-?\d+\.?\d*)\)', location_text)
        if match:
            lat = float(match.group(1))
            lng = float(match.group(2))
            return [lat, lng]
    except:
        pass
    return None

def calculate_distance(coord1, coord2):
    """
    Calculate the distance between two coordinates using Haversine formula
    Returns distance in kilometers
    """
    # Unpack coordinates
    lat1, lon1 = coord1
    lat2, lon2 = coord2

    # Radius of Earth in km
    R = 6371.0

    # Convert degrees to radians
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    # Haversine formula
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    a = max(0, min(1, a))  # Clamp a to [0, 1]
    c = 2 * math.asin(math.sqrt(a))

    distance = R * c
    return distance


def is_within_time_limit(timestamp_str, hours_limit=48):
    """
    Check if the incident timestamp is within the specified hours limit
    """
    try:
        # Parse the timestamp
        if isinstance(timestamp_str, str):
            # Handle ISO format with timezone
            if 'T' in timestamp_str:
                # Remove timezone info for parsing if present
                clean_timestamp = timestamp_str.split('+')[0].split('Z')[0]
                incident_time = datetime.fromisoformat(clean_timestamp)
            else:
                incident_time = datetime.fromisoformat(timestamp_str)
        else:
            return False
        
        # Calculate time difference
        current_time = datetime.now()
        time_diff = current_time - incident_time
        
        # Check if within the time limit
        return time_diff.total_seconds() <= (hours_limit * 3600)
    
    except Exception as e:
        # If we can't parse the timestamp, assume it's old
        return False

def filter_incidents_by_proximity_and_time(incidents, user_coords, max_distance_km=20, max_hours=48):
    """
    Filter incidents based on proximity to user location and time since reported
    """
    if not user_coords:
        return incidents  # Return all incidents if no user location
    
    filtered_incidents = []
    
    for incident in incidents:
        # Check coordinates
        incident_coords = extract_coordinates_from_location(incident.get('location', ''))
        if not incident_coords:
            continue
        
        # Check distance
        distance = calculate_distance(user_coords, incident_coords)
        if distance > max_distance_km:
            continue
        
        # Check time
        timestamp = incident.get('timestamp', '')
        if not is_within_time_limit(timestamp, max_hours):
            continue
        
        # Add distance info to incident for display
        incident['distance_km'] = round(distance, 2)
        filtered_incidents.append(incident)
    
    return filtered_incidents

def get_incident_color(category):
    """Return color based on incident category"""
    color_map = {
        "Accident": "red",
        "Fire": "orange", 
        "Protest / March": "beige",
        "Construction Work in Progress": "yellow",
        "Theft": "purple",
        "Crime": "red",
        "Waterlogging": "blue",
        "Others": "gray"
    }
    return color_map.get(category, "gray")

def get_incident_icon(category):
    """Return icon based on incident category"""
    icon_map = {
        "Accident": "🚗",
        "Fire": "🔥",
        "Protest / March": "👥",
        "Construction Work in Progress": "🚧",
        "Theft": "🥷",
        "Crime": "🦹",
        "Waterlogging": "🌊",
        "Others": "‼"
    }
    return icon_map.get(category, "‼")

def get_urgency_color(classification_text):
    """Extract urgency level and return appropriate color intensity"""
    if not classification_text:
        return 0.5
    
    classification_lower = classification_text.lower()
    if "urgency: high" in classification_lower:
        return 1.0
    elif "urgency: medium" in classification_lower:
        return 0.7
    elif "urgency: low" in classification_lower:
        return 0.4
    return 0.5

def parse_classification_info(classification_text):
    """Parse classification text to extract type, urgency, and severity"""
    if not classification_text:
        return {"type": "Unknown", "urgency": "Medium", "severity": "3"}
    
    info = {"type": "Unknown", "urgency": "Medium", "severity": "3"}
    lines = classification_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if line.startswith("Type:"):
            info["type"] = line.replace("Type:", "").strip()
        elif line.startswith("Urgency:"):
            info["urgency"] = line.replace("Urgency:", "").strip().title()
        elif line.startswith("Severity:"):
            info["severity"] = line.replace("Severity:", "").strip()
    
    return info

def format_time_ago(timestamp_str):
    """Format timestamp to show how long ago the incident was reported"""
    try:
        if 'T' in timestamp_str:
            clean_timestamp = timestamp_str.split('+')[0].split('Z')[0]
            incident_time = datetime.fromisoformat(clean_timestamp)
        else:
            incident_time = datetime.fromisoformat(timestamp_str)
        
        time_diff = datetime.now() - incident_time
        
        if time_diff.days > 0:
            return f"{time_diff.days}d ago"
        elif time_diff.seconds > 3600:
            hours = time_diff.seconds // 3600
            return f"{hours}h ago"
        elif time_diff.seconds > 60:
            minutes = time_diff.seconds // 60
            return f"{minutes}m ago"
        else:
            return "Just now"
    except:
        return "Unknown"





# Custom CSS
st.markdown("""
    <style>
        .main {
            font-family: 'Montserrat',;
        }

        .stTextInput label, .stFileUploader label, .stTextArea label, .stSelectbox label {
            font-size: 18px;
            font-weight: 600;
        }

        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 0.1rem;
        }

        .map-wrapper {
            margin-top: -20px;
        }
            /* Add this to your <style> block 
        .st-emotion-cache-z5fcl4 {
            width: 100%;
        }
        */
      
        .custom-row {
            display: flex;
            gap: 15px; /* Adjust the space between the boxes */
            margin-bottom: 15px;
        }


        .incident-legend, .stats-box {
            background-color: black;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 4px solid #007bff;
            flex: 1; /* This makes them share the space equally */
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        
        }

        .legend-item {
            display: flex;
            align-items: center;
            margin: 8px 0;
            font-size: 14px;
        }

        .legend-color {
            width: 18px;
            height: 18px;
            border-radius: 50%;
            margin-right: 10px;
            border: 2px solid #333;
        }
        
        .filter-info {
            background-color: black;
            padding: 10px;
            border-radius: 8px;
            margin: 10px 0;
            border-left: 4px solid #2196f3;
        }
    </style>
""", unsafe_allow_html=True)

# Session state initialization
if "auto_location_used" not in st.session_state:
    st.session_state.auto_location_used = False
if "location_coords" not in st.session_state:
    st.session_state.location_coords = None

# ---------------- LAYOUT ----------------
left_col, right_col = st.columns([1, 2.5])

# ---------------- RIGHT PANEL ----------------
with right_col:
    st.markdown('<div class="map-wrapper">', unsafe_allow_html=True)
    
    # Fetch incidents from Firebase
    with st.spinner("🔄 Loading incident data from database..."):
        all_incidents = fetch_incidents_from_firebase()
    
    location_data = streamlit_geolocation()

    # Default map center (Kolkata/Howrah area based on your location)
    default_center = [22.5726, 88.3639]  # Kolkata coordinates
    map_center = default_center
    user_coords = None

    if location_data and location_data.get("latitude") and location_data.get("longitude"):
        user_coords = [location_data["latitude"], location_data["longitude"]]
        st.session_state.auto_location_used = True
        st.session_state.location_coords = user_coords
        map_center = user_coords
        #st.success(f"📍 Location detected: {user_coords[0]:.4f}, {user_coords[1]:.4f}")
    else:
        st.session_state.auto_location_used = False
        #st.warning("🔍 Enable location access to see nearby recent incidents")
    
    # Filter incidents based on proximity and time
    if user_coords:
        filtered_incidents = filter_incidents_by_proximity_and_time(
            all_incidents, user_coords, max_distance_km=25, max_hours=48
        )
        
    else:
        filtered_incidents = all_incidents
        st.info("📍 Enable location access to see filtered nearby incidents (within 25 km, last 48 hours)")

    st.header(f"🗺 Live Incident Map ({len(filtered_incidents)} Recent Nearby Incidents)")
    
    # Add legend and statistics
    m = folium.Map(location=map_center, zoom_start=15 if user_coords else 12)
    
    # Add user's current location marker if available
    m = folium.Map(location=map_center, zoom_start=15 if user_coords else 12)
        
        # Add user's current location marker if available
    if user_coords:
            folium.Marker(
                user_coords,
                popup=folium.Popup("📍 Your Current Location", max_width=400),
                tooltip="Your Location",
                icon=folium.Icon(color="pink", icon="user", prefix='fa')
            ).add_to(m)
            
            # Add a circle to show the 15 km radius
            folium.Circle(
                user_coords,
                radius=25000,  # 15km in meters
                popup="25 km radius filter",
                color="blue",
                fillColor="cadetblue",
                fillOpacity=0.1,
                weight=2,
                dashArray="5, 5"
            ).add_to(m)

    # Add filtered incident markers
    incident_count = 0

    if filtered_incidents:
            for incident in filtered_incidents:
                coords = extract_coordinates_from_location(incident.get('location', ''))
                if coords:
                    incident_count += 1
                    category = incident.get('category', 'Others')
                    description = incident.get('description', 'No description')
                    timestamp = incident.get('timestamp', 'Unknown time')
                    classification = incident.get('classification', '')
                    routing = incident.get('routing', '')
                    suggestions = incident.get('suggestions', '')
                    status = incident.get('status', 'Pending')
                    distance = incident.get('distance_km', 0)
                    time_ago = format_time_ago(timestamp)
                    
                    # Parse classification info
                    class_info = parse_classification_info(classification)
                    
                    # Create detailed popup content with distance and time info
                    popup_content = f"""
                    <div style="width: 300px; max-height: 450px; overflow-y: auto;">
                        <h4 style="color: {get_incident_color(category)}; margin-bottom: 10px;">
                            {category} 
                            <span style="background-color: {'#ff4444' if class_info['urgency'] == 'High' else '#ffa500' if class_info['urgency'] == 'Medium' else '#90EE90'}; 
                                         color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px;">
                                {class_info['urgency'].upper()}
                            </span>
                        </h4>
                        <p><b>⏰ Reported:</b> {time_ago}</p>
                        <p><b>📏 Distance:</b> {distance}km away</p>
                        <p><b>📅 Time:</b> {timestamp[:19] if len(timestamp) > 19 else timestamp}</p>
                        <p><b>📍 Location:</b> {coords[0]:.4f}, {coords[1]:.4f}</p>
                        <p><b>📝 Description:</b> {description[:150]}{'...' if len(description) > 150 else ''}</p>
                        <p><b>🏷 Classification:</b> {class_info['type']}</p>
                        <p><b>⚡ Urgency:</b> {class_info['urgency']} | <b>📊 Severity:</b> {class_info['severity']}/5</p>
                        <p><b>📈 Status:</b> <span style="color: {'green' if status == 'Resolved' else 'orange'};">{status}</span></p>
                        {f'<p><b>🎯 Routing:</b> {routing}</p>' if routing else ''}
                        {f'<p><b>💡 AI Suggestions:</b> {suggestions[:100]}{"..." if len(suggestions) > 100 else ""}</p>' if suggestions else ''}
                    </div>
                    """
                    
                    # Add incident marker with enhanced styling
                    emoji = get_incident_icon(category)
                    color = get_incident_color(category)

                    # Define the HTML for the custom emoji icon
                    icon_html = f"""
                    <div style="
                        font-size: 1.5rem;
                        background-color: {color};
                        width: 2.5rem;
                        height: 2.5rem;
                        border-radius: 50%;
                        text-align: center;
                        line-height: 2.5rem;
                        color: white;
                        border: 2px solid white;
                        box-shadow: 0 0 5px rgba(0,0,0,0.5);
                        ">
                        {emoji}
                    </div>
                    """

                    # Add the marker to the map using folium.DivIcon
                    folium.Marker(
                        coords,
                        popup=folium.Popup(popup_content, max_width=320),
                        tooltip=f"{category} - {class_info['urgency']} Priority - {time_ago} - {distance}km away",
                        icon=folium.DivIcon(html=icon_html)
                    ).add_to(m)
        
    map_data = st_folium(m,width=2000, height=640, returned_objects=["last_object_clicked"])

    if filtered_incidents:
        # Calculate statistics
        category_counts = {}
        urgency_counts = {"High": 0, "Medium": 0, "Low": 0}

        for incident in filtered_incidents:
            category = incident.get('category', 'Others')
            category_counts[category] = category_counts.get(category, 0) + 1

            classification = parse_classification_info(incident.get('classification', ''))
            urgency = classification.get('urgency', 'Medium')
            urgency_counts[urgency] = urgency_counts.get(urgency, 0) + 1

        # Calculate average distance if user location is available
        avg_distance = 0
        if user_coords and filtered_incidents:
            total_distance = sum(incident.get('distance_km', 0) for incident in filtered_incidents)
            avg_distance = total_distance / len(filtered_incidents)

        st.markdown('<div class="custom-row">', unsafe_allow_html=True)
        stats_col, legend_col = st.columns([1, 1])
        with stats_col:
            st.markdown(f"""
            <div class="stats-box">
                <h4>📊 Nearby Recent Stats</h4>
                <p><strong>🔥 High Priority:</strong> {urgency_counts.get('High', 0)}</p>
                <p><strong>⚡ Medium Priority:</strong> {urgency_counts.get('Medium', 0)}</p>
                <p><strong>📝 Low Priority:</strong> {urgency_counts.get('Low', 0)}</p>
                <p><strong>🏆 Most Common:</strong> {max(category_counts, key=category_counts.get) if category_counts else 'None'}</p>
                {f'<p><strong>📏 Avg Distance:</strong> {avg_distance:.1f}km</p>' if user_coords else ''}
            </div>
            """, unsafe_allow_html=True)

        with legend_col:
            st.markdown("""
            <div class="incident-legend">
                <h4>🗺 Map Legend</h4>
                <div class="legend-columns">  <!-- This is the new wrapper -->
                    <div class="legend-column"> <!-- First column -->
                        <div class="legend-item">
                            <div class="legend-color" style="background-color: pink;"></div>
                            <span>Your Current Location</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color" style="background-color: red; border-color: red;"></div>
                            <span>🚗 Accident</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color" style="background-color: orange; border-color: orange;"></div>
                            <span>🔥 Fire</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color" style="background-color: beige; border-color: beige;"></div>
                            <span>👥 Protest / March</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color" style="background-color: yellow; border-color: yellow;"></div>
                            <span>🚧 Construction</span>
                        </div>
                    </div>
                    <div class="legend-column"> <!-- Second column -->
                        <div class="legend-item">
                            <div class="legend-color" style="background-color: purple; border-color: purple;"></div>
                            <span>🥷 Theft</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color" style="background-color: red; border-color: red;"></div>
                            <span>🦹 Crime</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color" style="background-color: blue; border-color: blue;"></div>
                            <span>🌊 Waterlogging</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color" style="background-color: gray; border-color: gray;"></div>
                            <span>‼ Others</span>
                        </div>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True) 

    # Display incident statistics
    if user_coords:
        if incident_count > 0:
            st.success(f"📊 Displaying {incident_count} recent incidents within 25 km on the map")
        else:
            st.success("✅ No recent incidents found nearby - area seems safe!")
    else:
        if incident_count > 0:
            st.info(f"📊 Displaying {incident_count} total incidents (Enable location for proximity filtering)")
        else:
            st.info("📊 No incidents found in database")

    # Auto-refresh button
    if st.button("🔄 Refresh Map Data", key="refresh_map"):
        st.cache_data.clear()
        st.rerun()

    # Display clicked incident details in sidebar
    if map_data["last_object_clicked"]:
        clicked_data = map_data["last_object_clicked"]
        if clicked_data and "lat" in clicked_data and "lng" in clicked_data:
            clicked_coords = [clicked_data["lat"], clicked_data["lng"]]
            
            # Find the incident that matches these coordinates
            for incident in filtered_incidents:
                incident_coords = extract_coordinates_from_location(incident.get('location', ''))
                if incident_coords and abs(incident_coords[0] - clicked_coords[0]) < 0.001 and abs(incident_coords[1] - clicked_coords[1]) < 0.001:
                    st.sidebar.markdown("### 📋 Selected Incident Details")
                    st.sidebar.markdown(f"🏷 Category:** {incident.get('category', 'Unknown')}")
                    st.sidebar.markdown(f"⏰ Reported:** {format_time_ago(incident.get('timestamp', ''))}")
                    st.sidebar.markdown(f"📏 Distance:** {incident.get('distance_km', 0)}km away")
                    st.sidebar.markdown(f"📅 Time:** {incident.get('timestamp', 'Unknown')}")
                    st.sidebar.markdown(f"📍 Location:** {incident.get('location', 'Unknown')}")
                    st.sidebar.markdown(f"📝 Description:** {incident.get('description', 'No description')}")
                    
                    classification = incident.get('classification', '')
                    if classification:
                        st.sidebar.markdown("🤖 AI Analysis:")
                        st.sidebar.code(classification)
                    
                    routing = incident.get('routing', '')
                    if routing:
                        st.sidebar.markdown(f"🎯 Routing:** {routing}")
                    
                    authority_routing = incident.get('authority_routing', '')
                    if authority_routing and authority_routing != "No authority routing required":
                        st.sidebar.markdown(f"🏛 Authorities Notified:** {authority_routing}")
                    
                    suggestions = incident.get('suggestions', '')
                    if suggestions:
                        st.sidebar.markdown("💡 AI Safety Suggestions:")
                        st.sidebar.write(suggestions[:300] + "..." if len(suggestions) > 300 else suggestions)
                    
                    status = incident.get('status', 'Pending')
                    st.sidebar.markdown(f"📈 Status:** {status}")
                    break

    st.markdown('</div>', unsafe_allow_html=True)

# ---------------- LEFT PANEL ----------------
with left_col:
    st.header("📝 Report New Incident")

    uploaded_media = st.file_uploader(
        "📷 UPLOAD PHOTOS/VIDEOS",
        type=["jpg", "jpeg", "png", "mp4", "mov", "avi", "mkv"],
        accept_multiple_files=True,
        help="Upload evidence photos or videos of the incident"
    )

    incident_type = st.selectbox(
        "🏷 TYPE OF INCIDENT",
        ["Accident", "Fire", "Protest / March", "Construction Work in Progress", "Theft", "Crime", "Waterlogging", "Others"],
        help="Select the category that best describes the incident"
    )

    # Location text field gets auto-filled when detected
    default_location = "Using current location" if st.session_state.auto_location_used else ""
    location_text = st.text_input(
        "📍 LOCATION", 
        value=default_location,
        help="Describe the location or let GPS auto-detect"
    )

    description = st.text_area(
        "📝 DETAILED DESCRIPTION",
        help="Provide as much detail as possible about what happened",
        height=120
    )
    
    submit = st.button("🚨 Submit Report", type="primary", use_container_width=True)

    # Show nearby incidents from filtered data
    if st.session_state.location_coords and filtered_incidents:
        st.markdown("### 🔍 Recent Nearby Incidents")
        user_coords = st.session_state.location_coords
        
        # Sort by distance
        nearby_sorted = sorted(filtered_incidents, key=lambda x: x.get('distance_km', 0))
        
        if nearby_sorted:
            st.info(f"Found {len(nearby_sorted)} recent incidents within 30 km (last 48 hours)")
            for i, incident in enumerate(nearby_sorted[:3]):  # Show top 3 nearby
                class_info = parse_classification_info(incident.get('classification', ''))
                urgency_emoji = "🔥" if class_info['urgency'] == 'High' else "⚡" if class_info['urgency'] == 'Medium' else "📝"
                time_ago = format_time_ago(incident.get('timestamp', ''))
                distance = incident.get('distance_km', 0)
                
                with st.expander(f"{urgency_emoji} {incident.get('category', 'Unknown')} - {time_ago} - {distance}km away"):
                    st.write(f"📝 Description:** {incident.get('description', 'No description')}")
                    st.write(f"📍 Location:** {incident.get('location', 'Unknown')}")
                    st.write(f"⚡ Priority:** {class_info['urgency']}")
                    st.write(f"📏 Distance:** {distance}km from your location")
                    st.write(f"⏰ Reported:** {time_ago}")
                    st.write(f"📈 Status:** {incident.get('status', 'Pending')}")
        else:
            st.success("✅ No recent incidents reported nearby - area seems safe!")

# ---------------- SUBMISSION LOGIC ----------------
if submit:
    latlng = st.session_state.location_coords
    if not uploaded_media or not location_text or not description or not latlng:
        st.warning("⚠ Please complete all fields and ensure location is enabled before submitting.")
    else:
        try:
            #for prgress bar
            st.markdown("### 🚀 Submitting your report...")
            prg = st.progress(0)

            for i in range(100):
                time.sleep(1.8)
                prg.progress(i+1)
            files = []
            for media in uploaded_media:
                files.append(("file", (media.name, media, media.type)))
            # storing the input data to backend using fastapi
            response = requests.post(
                f"{BACKEND_URL}/report/",
                data={
                    "category": incident_type,
                    "location": f"{location_text} ({latlng[0]}, {latlng[1]})",
                    "description": description
                },
                files=files
            )


            if response.status_code == 200:
                st.success("✅ Incident reported successfully and saved to database!")
                response_data = response.json()
                
                # Display AI analysis results
                if "ai_data" in response_data:
                    ai_data = response_data["ai_data"]
                    st.markdown("### 🤖 AI Analysis Results")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if "classification" in ai_data:
                            st.markdown("📊 Classification:")
                            st.code(ai_data["classification"])
                    
                    with col2:
                        if "routing" in ai_data:
                            st.markdown(f"🎯 Routing:** {ai_data['routing']}")
                        if "authority_routing" in ai_data and ai_data["authority_routing"] != "No authority routing required":
                            st.markdown(f"🏛 Authorities Notified:** {ai_data['authority_routing']}")
                    
                    if "suggestions" in ai_data:
                        st.markdown("💡 AI Safety Suggestions:")
                        st.info(ai_data["suggestions"])
                
                # Auto-refresh to show new incident
               
                st.cache_data.clear()  # Clear cache to show new data
                if st.button("🔄 Refresh Map to See Your Report"):
                    st.rerun()
                
            else:
                st.error(f"❌ Error: {response.status_code}")
                st.text(response.text)

        except Exception as e:
            st.error(f"❌ Failed to connect to backend: {e}")

        report_time = datetime.now(timezone.utc)

        st.markdown("### 📄 Report Summary")
        st.markdown(f"🏷 Type:** {incident_type}")
        st.markdown(f"📍 Location:** {location_text}")
        st.markdown(f"📝 Description:** {description}")
        st.markdown(f"📅 Reported at:** {report_time}")
        st.markdown(f"🌐 Coordinates:** {latlng[0]:.6f}, {latlng[1]:.6f}")

        # Create summary DataFrame for download
        summary_df = pd.DataFrame([{
            "Type": incident_type,
            "Location": location_text,
            "Description": description,
            "Reported at": report_time,
            "Latitude": latlng[0],
            "Longitude": latlng[1]
        }])

        csv_buffer = StringIO()
        summary_df.to_csv(csv_buffer, index=False)

        st.download_button(
                label="💾 Download Report Summary",
                data=csv_buffer.getvalue(),
                file_name=f"incident_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )

# ---------------- FOOTER ----------------
st.markdown("""
<style>
.footer {
    text-align: center;
    padding: 25px;
    margin-top: 40px;
    border-top: 1px solid #222; /* A subtle top border */
    background-color: #0E1117; /* Matches Streamlit's dark theme background */
    border-radius: 10px;
    box-shadow: 0 -4px 10px rgba(0, 0, 0, 0.2); /* A soft shadow at the top */
}
.footer-title {
    font-size: 1.25em; /* Larger font for the main title */
    font-weight: 700;  /* Bolder text */
    color: #FAFAFA;   /* Bright text color */
    margin-bottom: 3px;
}
.footer-credits {
    font-size: 1em;    /* Standard font size for credits */
    color: #A0A0A0;   /* A slightly dimmer color for subtlety */
    margin: 0;
}
</style>

<div class="footer">
    <p class="footer-title">🛡️ Suraksha Setu - Community Safety Reporting System</p>
    <p class="footer-credits">🙇 Powered by Neuronauts: Anirban, Jyotiraditya, Subarna, Pushkar</p>
</div>
""", unsafe_allow_html=True)  
