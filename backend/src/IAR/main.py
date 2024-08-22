from langchain_aws import ChatBedrock
from pydantic import BaseModel, Field
import base64
from langchain_core.messages import HumanMessage
from typing import List, Dict
import os
import re 
import json

llm = ChatBedrock(
    model_id="anthropic.claude-3-sonnet-20240229-v1:0",
    model_kwargs={"temperature": 0},
    region_name="ap-south-1",
)
 
class DamageReport(BaseModel):
    image_name: str = Field(description="Name of the image")
    damage_parts: List[str] = Field(description="List of damaged parts")
 
conditions_report_initial_prompt = """You are an expert automotive inspector specializing in assessing damages from car accidents.
Analyze the provided images of the damaged car and identify all types of damages visible.
For each image, analyze and provide a detailed list of car components that show visible damage.
Only include those components where damage is detected.
RHS is Driver's side and LHS is passenger side of car so based on this decide the damage side of car.
Use the following parts list to specify the damaged components and their condition:
Parts List:
 Front bumper.
 Front grille upper.
 Front grille lower.
 Hood (Bonnet).
 Front Windshield Glass.
 Side View Mirror RHS.
 Side View Mirror LHS.
 Headlamp RHS.
 Headlamp LHS.
 Fog lamp RHS.
 Fog lamp LHS.
 Fender RHS.
 Door Front RHS.
 Door Rear RHS.
 Quarter Panel RHS.
 Tail lamp RHS.
 Rear Bumper.
 Tail Gate (Dicky).
 Rear Windscreen Glass.
 Tail Lamp LHS.
 Quarter Panel LHS.
 Door Rear LHS.
 
For each detail, calculate the damage score, on the basis of score classify only one category below donot include score:
- Dent
- Scratch
- Cracked
- Broken
 
"""

def parse_damage_report(report: str, image_mapping: Dict[str, str]) -> Dict[str, List[str]]:
    parsed_report = {}
    sections = re.split(r'\n(?=Image \d+:)', report.strip())
   
    for section in sections:
        lines = section.split('\n')
        image_name = lines[0].strip()
        damages = [line.strip() for line in lines[1:] if line.strip()]
        # Correct the image name using the mapping
        if image_name in image_mapping:
            image_name = image_mapping[image_name]
        parsed_report[image_name] = damages
   
    return parsed_report

# @logger.inject_lambda_context(log_event=True)
def lambda_handler(event, context):
    folder_path = r'/home/ubuntu/car-damage-assessment/Motor Vehicles/4'

    # Step 1: Associate image numbers with filenames
    image_mapping = {}
    encoded_images = []
    for i, filename in enumerate(sorted(os.listdir(folder_path)), 1):
        if filename.endswith(('.png', '.jpg', '.jpeg')):
            image_mapping[f"Image {i}"] = filename
            with open(os.path.join(folder_path, filename), 'rb') as image_file:
                encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
                encoded_images.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": encoded_image},
                })

    # Step 2: Send the images with corresponding image numbers in the prompt
    message = HumanMessage(
        content=[
            {"type": "text", "text": conditions_report_initial_prompt},
            *encoded_images
        ]
    )

    # Invoke the model
    llm_out = llm.invoke([message])
    
    # Extract content from AIMessage
    if hasattr(llm_out, 'content'):
        report_content = llm_out.content
    else:
        report_content = str(llm_out)  # Fallback if content attribute is not found
    
    # Parse the report
    parsed_report = parse_damage_report(report_content, image_mapping)

    # Print the parsed report
    for image, damages in parsed_report.items():
        print(f"{image}:")
        for damage in damages:
            print(f"  - {damage}")
    
    output_string = ""
 
    # Loop through the parsed report and append each line to the output_string
    for image, damages in parsed_report.items():
        output_string += f"{image}:\n"
        for damage in damages:
            output_string += f"  - {damage}\n"


    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
        },
        "body": json.dumps(output_string),
    }
