#from langchain_ollama.llms import OllamaLLM
from langchain.prompts import ChatPromptTemplate
from datetime import datetime, timezone, timedelta
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
# Initialize Gemini API
geminiapi = os.getenv("GEMINI_API_KEY")
# Set your Gemini API Key
genai.configure(api_key=geminiapi)

# Instantiate genai model
llm = genai.GenerativeModel("gemini-1.5-flash-latest")

def input_agent(category, location, description):
    """Parse and structure input data"""
    # Convert UTC time to IST (Indian Standard Time, UTC+5:30)
    utc_now = datetime.now(timezone.utc)
    ist_now = utc_now + timedelta(hours=5, minutes=30)
    return {
        "category": category,
        "location": location,
        "description": description,
        "submitted_at": ist_now.isoformat()
    }

def classification_agent(parsed):
    """Classify incident type, urgency, and severity"""
    try:
        prompt = ChatPromptTemplate.from_template(
            """You are an incident classification system. Analyze the following incident and classify it into ONE of these exact categories:

INCIDENT CATEGORIES (choose exactly one):
- Accident
- Crime
- Waterlogging
- Construction Work in Progress
- Fire
- Protest / March
- Others

Incident Details:
Description: {description}
Category: {category}
Location: {location}

Classification Guidelines:
- Accident: Vehicle crashes, falls, injuries, collisions
- Crime: Theft, assault, vandalism, illegal activities
- Waterlogging: Flooding, water accumulation, drainage issues
- Construction Work in Progress: Road work, building construction, infrastructure development
- Fire: Fires, smoke, burning incidents
- Protest / March: Demonstrations, rallies, marches, crowds, stampedes
- Others: Anything that doesn't fit the above categories

Urgency Guidelines:
- low: Minor issues, no immediate danger
- medium: Moderate concern, some disruption
- high: Serious situation, immediate attention needed

Severity Guidelines:
- 1: Very minor, minimal impact
- 2: Minor, limited impact
- 3: Moderate, noticeable impact
- 4: Serious, significant impact
- 5: Critical, major impact or danger

Based on the incident description "{description}", provide your classification in this EXACT format:
Type: [choose one from the categories above]
Urgency: [low/medium/high]
Severity: [1/2/3/4/5]"""
        )
        
        formatted_prompt = prompt.format(
            description=parsed["description"],
            category=parsed["category"],
            location=parsed["location"]
        )
        
        response = llm.generate_content(prompts=[formatted_prompt])
        result = response.text.strip()
        
        # Validate and clean the response
        result = validate_classification_response(result, parsed)
        
        return result
        
    except Exception as e:
        return get_default_classification(parsed)

def validate_classification_response(response, parsed):
    """Validate and correct classification response"""
    valid_types = [
        "Accident", "Crime", "Waterlogging", 
        "Construction Work in Progress", "Fire", 
        "Protest / March", "Others"
    ]
    valid_urgency = ["low", "medium", "high"]
    valid_severity = ["1", "2", "3", "4", "5"]
    
    lines = response.split('\n')
    result_type = None
    result_urgency = None
    result_severity = None
    
    # Parse the response
    for line in lines:
        line = line.strip()
        if line.startswith("Type:"):
            type_value = line.replace("Type:", "").strip()
            for valid_type in valid_types:
                if valid_type.lower() in type_value.lower() or type_value.lower() in valid_type.lower():
                    result_type = valid_type
                    break
        elif line.startswith("Urgency:"):
            urgency_value = line.replace("Urgency:", "").strip().lower()
            if urgency_value in valid_urgency:
                result_urgency = urgency_value
        elif line.startswith("Severity:"):
            severity_value = line.replace("Severity:", "").strip()
            if severity_value in valid_severity:
                result_severity = severity_value
    
    # Fallback logic if parsing failed
    if not result_type:
        result_type = infer_type_from_description(parsed["description"], parsed["category"])
    if not result_urgency:
        result_urgency = infer_urgency_from_description(parsed["description"])
    if not result_severity:
        result_severity = infer_severity_from_description(parsed["description"])
    
    return f"Type: {result_type}\nUrgency: {result_urgency}\nSeverity: {result_severity}"

def infer_type_from_description(description, category):
    """Infer incident type from description and category"""
    desc_lower = description.lower()
    cat_lower = category.lower() if category else ""
    
    if any(word in desc_lower for word in ["march", "protest", "demonstration", "rally", "crowd", "stampede", "blockade", "sit-in"]):
        return "Protest / March"
    elif any(word in desc_lower for word in ["accident", "crash", "collision", "hit", "injury", "fall", "roadblock", "traffic jam"]):
        return "Accident"
    elif any(word in desc_lower for word in ["fire", "burn", "smoke", "flame", "explosion", "blaze", "gas leak", "toxic"]):
        return "Fire"
    elif any(word in desc_lower for word in ["flood", "water", "rain", "drainage", "waterlog", "standing water", "overflow"]):
        return "Waterlogging"
    elif any(word in desc_lower for word in ["construction", "work", "building", "road work", "repair", "infrastructure", "pavement", "digging"]):
        return "Construction Work in Progress"
    elif any(word in desc_lower for word in ["theft", "crime", "steal", "assault", "vandal", "illegal", "robbery", "burglary", "attack"]):
        return "Crime"
    elif "protest" in cat_lower or "march" in cat_lower:
        return "Protest / March"
    else:
        return "Others"

def infer_urgency_from_description(description):
    """Infer urgency from description keywords"""
    desc_lower = description.lower()
    
    high_urgency_words = ["emergency", "urgent", "critical", "danger", "stampede", "fire", "accident", "injured", "many injured", "crowd surge", "blocked", "panic"]
    low_urgency_words = ["minor", "small", "routine", "scheduled", "planned", "normal", "no immediate danger", "not serious", "not urgent", "not critical"]
    
    if any(word in desc_lower for word in high_urgency_words):
        return "high"
    elif any(word in desc_lower for word in low_urgency_words):
        return "low"
    else:
        return "medium"

def infer_severity_from_description(description):
    """Infer severity from description keywords"""
    desc_lower = description.lower()
    
    if any(word in desc_lower for word in ["critical", "major", "stampede", "emergency", "hundreds", "thousands", "massive", "severe", "catastrophic", "disaster"]):
        return "4"
    elif any(word in desc_lower for word in ["serious", "significant", "blocked", "crowd", "panic", "dangerous", "explosion", "fire", "injured", "injuries"]):
        return "3"
    elif any(word in desc_lower for word in ["minor", "small", "few", "limited", "not serious", "not critical", "not urgent", "not dangerous"]):
        return "2"
    else:
        return "3"

def get_default_classification(parsed):
    """Get appropriate default classification based on input"""
    incident_type = infer_type_from_description(parsed["description"], parsed["category"])
    urgency = infer_urgency_from_description(parsed["description"])
    severity = infer_severity_from_description(parsed["description"])
    
    return f"Type: {incident_type}\nUrgency: {urgency}\nSeverity: {severity}"

def routing_agent(parsed, classification):
    """Determine routing based on classification"""
    try:
        classification_data = parse_classification(classification)
        incident_type = classification_data.get('type', '').lower()
        urgency = classification_data.get('urgency', 'medium').lower()
        severity = int(classification_data.get('severity', '3'))
        
        should_notify_authorities = determine_authority_notification(incident_type, urgency, severity)
        
        if should_notify_authorities:
            routing = "community push notification;authority email"
        else:
            routing = "community push notification"
        
        return routing
        
    except Exception as e:
        return "community push notification"

def determine_authority_notification(incident_type, urgency, severity):
    """Determine if authorities should be notified"""
    # High severity incidents always notify authorities
    if severity >= 4:
        return True
    
    # Critical incident types with medium-high urgency
    critical_types = ["accident", "crime", "fire"]
    if any(critical_type in incident_type for critical_type in critical_types) and urgency in ["medium", "high"]:
        return True
    
    # Special cases for protests/marches
    if ("protest" in incident_type or "march" in incident_type) and (urgency == "high" or severity >= 4):
        return True
    
    return False

def suggestion_agent(parsed, classification):
    """Generate safety suggestions based on incident"""
    try:
        classification_data = parse_classification(classification)
        incident_type = classification_data.get('type', '').lower()
        urgency = classification_data.get('urgency', 'medium').lower()
        severity = int(classification_data.get('severity', '3'))
        
        # Get predefined suggestions
        predefined_suggestions = get_category_suggestions(incident_type)
        
        # Generate creative suggestions for complex cases
        if should_use_creative_suggestions(parsed, urgency, severity):
            creative_suggestions = generate_creative_suggestions(parsed, classification, incident_type, urgency, severity)
            return creative_suggestions if creative_suggestions else predefined_suggestions
        
        return predefined_suggestions
        
    except Exception as e:
        return get_default_suggestions(incident_type)

def get_category_suggestions(incident_type):
    """Get predefined suggestions based on incident category"""
    suggestions_map = {
        "accident": [
            "Create a safe buffer zone around the accident by parking 100 meters away if you must stop.",
            "Turn on hazard lights and use your vehicle to protect emergency responders if directed by police.",
            "Document the scene only if safe to do so, as it may help with traffic management.",
            "Share traffic updates on community WhatsApp groups to help others plan alternate routes.",
            "If you are a witness, note down key details like time, vehicle descriptions, and license plates for police.",
            "If you are a driver involved, exchange contact and insurance details with other parties.",
            "If you are a pedestrian, stay clear of the accident site and follow police instructions.",
            "If you are a business owner, inform employees and customers to avoid the area until cleared."
        ],
        
        "crime": [
            "If you witnessed the incident, note down key details like time, descriptions, and vehicle numbers for police.",
            "Inform nearby shop owners and security guards to increase vigilance in the area.",
            "Use buddy system when traveling through the area until police presence increases.",
            "Check on elderly neighbors who might be particularly vulnerable to similar incidents.",
            "Avoid sharing sensitive information on social media that could compromise ongoing investigations.",
            "If you feel unsafe, consider staying indoors until police have cleared the area.",
            "If you are a victim, do not confront the suspect; instead, seek safety and contact police immediately.",
            "If you are a business owner, review security camera footage and share it with police if requested."
        ],
        
        "waterlogging": [
            "Turn off electricity at the main switch if water enters your building to prevent electrocution.",
            "Use sandbags or plastic sheets to redirect water away from building entrances.",
            "Document water levels with photos and timestamps for insurance and municipal complaints.",
            "Coordinate with neighbors to share pumping equipment and monitor vulnerable residents.",
            "Avoid driving through waterlogged areas as it can damage your vehicle and create hazards.",
            "If you must walk through water, use waterproof boots and avoid submerged electrical hazards.",
            "Check local weather updates for further rain forecasts and prepare accordingly.",
            "If you are a resident, keep emergency supplies like food, water, and medicines ready in case of prolonged flooding."
        ],
        
        "construction work in progress": [
            "Download offline maps before traveling to navigate if GPS signals are disrupted by construction.",
            "Schedule important appointments for earlier in the day when construction activity is typically lower.",
            "Contact local businesses to confirm they're accessible before visiting the area.",
            "Report any unsafe construction practices or missing safety barriers to municipal authorities.",
            "If you are a worker, ensure all safety gear is worn and follow site protocols to avoid accidents.",
            "If you are a driver, follow detour signs carefully and allow extra travel time to avoid frustration.",
            "If you are a pedestrian, use designated walkways and follow construction signage to stay safe.",
            "If you are a resident, keep windows closed to avoid dust and noise pollution."
        ],
        
        "fire": [
            "Close all windows and doors facing the fire to prevent smoke and ember entry.",
            "Wet down nearby structures and vegetation if you have water access and it's safe to do so.",
            "Move vehicles away from the fire area as fuel tanks can explode and create additional hazards.",
            "Monitor wind direction changes and be prepared to evacuate quickly if fire spreads toward you.",
            "If you are in a building, stay low to avoid smoke inhalation and use a wet cloth over your mouth.",
            "If trapped, signal for help from a window using a bright cloth or flashlight.",
            "If you are a resident, check on neighbors, especially the elderly or those with mobility issues.",
            "If you are a business owner, secure your premises and assist customers in evacuating safely."
        ],
        
        "protest / march": [
            "Monitor local news and social media for real-time updates on protest movement and road closures.",
            "If you must pass through the area, dress neutrally and avoid carrying bags that might be searched.",
            "Keep emergency contacts ready and share your location with family members before entering the vicinity.",
            "If trapped in a crowd surge, protect your chest with crossed arms and move diagonally toward barriers or walls.",
            "If you are a bystander, maintain a safe distance and avoid engaging with protesters to prevent escalation.",
            "If you are a protester, follow organizers' instructions and avoid confrontations with police or counter-protesters.",
            "If you are a resident, stay indoors and keep windows closed to avoid tear gas or other irritants.",
            "If you are a business owner, secure your premises and consider temporary closures if safety is a concern."
        ],
        
        "others": [
            "Take photos or videos from a safe distance to help authorities understand the situation better.",
            "Check if anyone needs immediate assistance but ensure your own safety first.",
            "Share information with neighbors through community apps to keep everyone informed.",
            "Contact local media if the incident affects public services or transportation significantly.",
            "If you are a resident, stay indoors and avoid unnecessary travel until the situation is resolved.",
            "If you are a business owner, inform employees and customers about the situation and any necessary precautions.",
            "If you are a driver, follow detour signs and avoid the area until cleared.",
            "If you are a pedestrian, stay clear of the incident site and follow any police instructions."
        ]
    }
    
    # Find matching category and return suggestions
    for category, suggestion_list in suggestions_map.items():
        if category in incident_type:
            return " ".join(suggestion_list)
    
    return " ".join(suggestions_map["others"])

def should_use_creative_suggestions(parsed, urgency, severity):
    """Determine if creative suggestions should be used"""
    description = parsed["description"].lower()
    
    complex_indicators = [
        len(description.split()) > 15,
        urgency == "high",
        severity >= 4,
        any(word in description for word in ["turned into", "stampede", "blocked", "many", "crowd", "emergency", "panic", "danger", "critical"]),
        any(word in description for word in ["stadium", "bridge", "hospital", "school", "market", "shopping", "mall", "airport", "public transport"]),
        "100" in description or any(str(i) in description for i in range(50, 1000, 50))
    ]
    
    return sum(complex_indicators) >= 2

def generate_creative_suggestions(parsed, classification, incident_type, urgency, severity):
    """Generate contextual suggestions using LLM"""
    try:
        prompt = ChatPromptTemplate.from_template(
            """You are a safety expert providing specific, actionable advice for this incident.

INCIDENT DETAILS:
Description: {description}
Category: {category}
Location: {location}
Type: {incident_type}
Urgency: {urgency}
Severity: {severity}

Provide 3-4 specific, actionable suggestions tailored to THIS exact situation:
1. Consider the location, scale, and unique circumstances
2. Include both immediate safety actions and practical advice
3. Be creative but realistic
4. Consider different groups affected (drivers, pedestrians, residents, workers)
5. Include communication/coordination advice if relevant

Format as clear, actionable sentences separated by periods."""
        )
        
        formatted_prompt = prompt.format(
            description=parsed["description"],
            category=parsed["category"],
            location=parsed["location"],
            incident_type=incident_type,
            urgency=urgency,
            severity=severity
        )
        
        response = llm.generate_content(prompts=[formatted_prompt])
        result = response.text.strip()
        
        enhanced_result = enhance_suggestions_with_context(result, parsed, incident_type)
        
        return enhanced_result if enhanced_result else get_category_suggestions(incident_type)
        
    except Exception as e:
        return get_category_suggestions(incident_type)

def enhance_suggestions_with_context(suggestions, parsed, incident_type):
    """Add contextual enhancements to generated suggestions"""
    try:
        description = parsed["description"].lower()
        context_elements = []
        
        # Location-specific additions
        if "stadium" in description:
            context_elements.append("Stadium visitors should coordinate with event security and use designated emergency exits.")
        elif "bridge" in description or "road" in description:
            context_elements.append("Drivers should inform traffic apps like Google Maps to help others avoid the area.")
        elif "market" in description or "shopping" in description:
            context_elements.append("Shop owners should secure their premises and assist customers in finding safe exits.")
        elif "hospital" in description or "school" in description:
            context_elements.append("Hospital staff should prepare for potential patient influx and coordinate with emergency services.")
        elif "airport" in description:
            context_elements.append("Airport staff should follow emergency protocols and assist passengers in evacuating safely.")
        elif "public transport" in description:
            context_elements.append("Public transport operators should halt services in the affected area and inform passengers via announcements.")
        elif "mall" in description:
            context_elements.append("Mall management should activate emergency protocols and guide shoppers to safe exits.")
        else:
            context_elements.append("Residents should stay indoors and avoid unnecessary travel until the situation is resolved.")
        
        # Scale-specific additions
        if any(str(i) in description for i in range(50, 1000)) or "many" in description or "crowd" in description:
            context_elements.append("If you see someone in distress, form small groups to help rather than acting alone.")
        
        # Emergency-specific additions
        if "stampede" in description or "panic" in description:
            context_elements.append("Stay low, protect your chest and head, and move diagonally toward less crowded areas.")
        
        # Communication additions
        if "blocked" in description or "road" in description:
            context_elements.append("Use WhatsApp groups or local community apps to share real-time updates with neighbors.")
            
        # Urgency and severity context
        if "danger" in description or "critical" in description:
            context_elements.append("If you are a bystander, maintain a safe distance and avoid engaging with protesters or emergency responders.")
            
        # Emergency response context    
        if "emergency" in description or "critical" in description:
            context_elements.append("If you are a driver, follow detour signs and avoid the area until cleared.")
        
        if context_elements:
            return suggestions + " " + " ".join(context_elements)
        
        return suggestions
        
    except Exception as e:
        return suggestions

def get_default_suggestions(incident_type=""):
    """Get default suggestions when other methods fail"""
    if not incident_type:
        return "Stay alert and follow official guidance. Report any concerning developments to authorities."
    
    incident_type = incident_type.lower()
    
    default_map = {
        "protest": "Avoid the area and use alternative routes. Stay calm and follow police instructions if in the vicinity.",
        "march": "Avoid the area and use alternative routes. Stay calm and follow police instructions if in the vicinity.",
        "accident": "Avoid the accident site and allow emergency services to work. Use alternative routes.",
        "fire": "Stay away from the fire area and report to emergency services if not already done.",
        "crime": "Avoid the affected area and report any suspicious activities to police.",
        "construction": "Follow detour signs and allow extra travel time. Stay alert for construction vehicles.",
        "water": "Avoid waterlogged areas and do not attempt to walk or drive through standing water."
    }
    
    for key, suggestion in default_map.items():
        if key in incident_type:
            return suggestion
    
    return "Stay alert and follow official guidance. Report any concerning developments to authorities."

def feedback_agent(parsed, classification, routing, user_feedback):
    """Process user feedback to improve classification"""
    try:
        prompt = ChatPromptTemplate.from_template(
            """Review and improve the incident classification based on user feedback:

Original Incident: {description}
Original Classification: {classification}
Original Routing: {routing}
User Feedback: {user_feedback}

Available incident types: Accident, Crime, Waterlogging, Construction Work in Progress, Fire, Protest / March, Others

Provide an improved classification considering the user's input. Format as:
Type: [type]
Urgency: [level]
Severity: [number]
Reasoning: [brief explanation]"""
        )
        
        formatted_prompt = prompt.format(
            description=parsed["description"],
            classification=classification,
            routing=routing,
            user_feedback=user_feedback
        )
        
        response = llm.generate_content(prompts=[formatted_prompt])
        result = response.text.strip()
        return result
        
    except Exception as e:
        return f"Error processing feedback: {str(e)}"

def authority_routing_agent(parsed, classification, routing):
    """Route to specific authorities when authority notification is required"""
    try:
        # Only route to authorities if the routing indicates authority notification
        if "authority email" not in routing:
            return "No authority routing required"
        
        classification_data = parse_classification(classification)
        incident_type = classification_data.get('type', '').lower()
        urgency = classification_data.get('urgency', 'medium').lower()
        severity = int(classification_data.get('severity', '3'))
        description = parsed["description"].lower()
        
        # Determine specific authorities based on incident type and context
        authorities = determine_specific_authorities(incident_type, urgency, severity, description)
        
        # Use LLM for complex cases requiring multiple authorities
        if should_use_llm_authority_routing(incident_type, description, authorities):
            llm_authorities = llm_authority_routing(parsed, classification, authorities)
            if llm_authorities:
                authorities = llm_authorities
        
        return format_authority_routing(authorities)
        
    except Exception as e:
        # Fallback to police for any authority routing errors
        return "Police Department"

def determine_specific_authorities(incident_type, urgency, severity, description):
    """Determine specific authorities based on incident characteristics"""
    authorities = []
    
    # Primary authority mapping based on incident type
    primary_authority_map = {
        "accident": ["Police Department", "Department of Medical Emergency"],
        "crime": ["Police Department"],
        "fire": ["Department of Fire and Emergency Services", "Department of Medical Emergency"],
        "waterlogging": ["Department of Disaster Relief"],
        "construction work in progress": ["Department of Traffic Police"],
        "protest / march": ["Police Department", "Department of Traffic Police"],
        "others": ["Police Department"]
    }
    
    # Get primary authorities for incident type
    for incident_key, authority_list in primary_authority_map.items():
        if incident_key in incident_type:
            authorities.extend(authority_list)
            break
    
    # Add additional authorities based on context and severity
    authorities.extend(get_contextual_authorities(description, urgency, severity))
    
    # Remove duplicates while preserving order
    seen = set()
    unique_authorities = []
    for auth in authorities:
        if auth not in seen:
            unique_authorities.append(auth)
            seen.add(auth)
    
    return unique_authorities if unique_authorities else ["Police Department"]

def get_contextual_authorities(description, urgency, severity):
    """Add authorities based on specific context clues in description"""
    additional_authorities = []
    
    # Medical emergency indicators
    medical_keywords = ["injured", "hurt", "ambulance", "medical", "hospital", "unconscious", "bleeding"]
    if any(keyword in description for keyword in medical_keywords):
        additional_authorities.append("Department of Medical Emergency")
    
    # Traffic disruption indicators
    traffic_keywords = ["blocked", "traffic", "road", "highway", "junction", "signal", "vehicle"]
    if any(keyword in description for keyword in traffic_keywords):
        additional_authorities.append("Department of Traffic Police")
    
    # Fire/explosion indicators
    fire_keywords = ["explosion", "gas leak", "chemical", "toxic", "smoke", "burning"]
    if any(keyword in description for keyword in fire_keywords):
        additional_authorities.append("Department of Fire and Emergency Services")
    
    # Disaster/infrastructure indicators
    disaster_keywords = ["collapse", "building", "infrastructure", "evacuation", "rescue", "trapped"]
    if any(keyword in description for keyword in disaster_keywords):
        additional_authorities.append("Department of Disaster Relief")
    
    # Large scale incidents (multiple authorities needed)
    scale_keywords = ["100", "many", "crowd", "stampede", "mass", "multiple"]
    if any(keyword in description for keyword in scale_keywords):
        additional_authorities.extend([
            "Department of Medical Emergency",
            "Department of Disaster Relief"
        ])
    
    # High severity incidents need comprehensive response
    if severity >= 4:
        additional_authorities.extend([
            "Department of Medical Emergency",
            "Department of Disaster Relief"
        ])
    
    return additional_authorities

def should_use_llm_authority_routing(incident_type, description, current_authorities):
    """Determine if LLM should be used for complex authority routing decisions"""
    
    # Use LLM for complex scenarios
    complex_indicators = [
        len(current_authorities) >= 3,  # Multiple authorities already identified
        "multiple" in description or "various" in description,
        any(word in description for word in ["chemical", "toxic", "explosion", "terror", "bomb"]),
        any(word in description for word in ["hospital", "school", "stadium", "mall", "airport"]),
        "stampede" in description,
        len(description.split()) > 20  # Detailed descriptions
    ]
    
    return sum(complex_indicators) >= 2

def llm_authority_routing(parsed, classification, current_authorities):
    """Use LLM to determine optimal authority routing for complex incidents"""
    try:
        prompt = ChatPromptTemplate.from_template(
            """You are an emergency response coordinator. Analyze this incident and determine which specific authorities should be notified.

INCIDENT DETAILS:
Description: {description}
Location: {location}
Classification: {classification}
Currently Identified Authorities: {current_authorities}

AVAILABLE AUTHORITIES:
- Police Department: General law enforcement, crime, crowd control, security
- Department of Fire and Emergency Services: Fires, explosions, hazardous materials, technical rescue
- Department of Traffic Police: Traffic management, road accidents, vehicle-related incidents
- Department of Disaster Relief: Natural disasters, evacuations, large-scale emergencies, infrastructure collapse
- Department of Medical Emergency: Medical emergencies, injuries, ambulance services, health hazards

ANALYSIS REQUIREMENTS:
1. Consider the primary nature of the incident
2. Identify secondary risks and complications
3. Think about resource coordination needs
4. Consider public safety implications
5. Account for potential escalation

Based on this incident, which authorities should be notified? List them in order of priority.
Respond with ONLY the authority names, separated by commas. Maximum 4 authorities."""
        )
        
        formatted_prompt = prompt.format(
            description=parsed["description"],
            location=parsed["location"],
            classification=classification,
            current_authorities=", ".join(current_authorities)
        )
        
        response = llm.generate_content(prompts=[formatted_prompt])
        result = response.text.strip()
        
        # Parse and validate the LLM response
        authorities = parse_llm_authority_response(result)
        return authorities if authorities else current_authorities
        
    except Exception as e:
        return current_authorities

def parse_llm_authority_response(response):
    """Parse and validate LLM authority routing response"""
    valid_authorities = [
        "Police Department",
        "Department of Fire and Emergency Services", 
        "Department of Traffic Police",
        "Department of Disaster Relief",
        "Department of Medical Emergency"
    ]
    
    # Clean and split the response
    authorities = []
    response_parts = response.replace('\n', ',').split(',')
    
    for part in response_parts:
        part = part.strip()
        # Find matching authority
        for valid_auth in valid_authorities:
            if valid_auth.lower() in part.lower() or part.lower() in valid_auth.lower():
                if valid_auth not in authorities:  # Avoid duplicates
                    authorities.append(valid_auth)
                break
    
    return authorities[:4]  # Limit to maximum 4 authorities

def format_authority_routing(authorities):
    """Format authority routing for consistent output"""
    if not authorities:
        return "Police Department"
    
    if len(authorities) == 1:
        return authorities[0]
    else:
        return "; ".join(authorities)

def run_pipeline(category, location, description):
    """Execute the complete agent pipeline for Streamlit"""
    try:
        # Step 1: Parse input
        parsed = input_agent(category, location, description)
        
        # Step 2: Classify incident
        classification = classification_agent(parsed)
        
        # Step 3: Determine routing
        routing = routing_agent(parsed, classification)
        
        # Step 4: Route to specific authorities (if needed)
        authority_routing = authority_routing_agent(parsed, classification, routing)
        
        # Step 5: Generate suggestions
        suggestions = suggestion_agent(parsed, classification)
        
        result = {
            **parsed,
            "classification": classification,
            "routing": routing,
            "authority_routing": authority_routing,
            "suggestions": suggestions
        }
        
        return result
        
    except Exception as e:
        # Return basic structure even if pipeline fails
        return {
            "category": category,
            "location": location,
            "description": description,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "classification": "Error in classification",
            "routing": "community push notification",
            "authority_routing": "Police Department",
            "suggestions": "Please contact local authorities for assistance."
        }

def parse_classification(classification_text):
    """Parse classification text into structured data"""
    try:
        lines = classification_text.split('\n')
        result = {}
        for line in lines:
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                result[key] = value
        return result
    except Exception:
        return {"type": "others", "urgency": "medium", "severity": "3"}