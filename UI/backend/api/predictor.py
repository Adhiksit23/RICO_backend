from fastapi import APIRouter

router = APIRouter(
    prefix="/api/predictor",
    tags=["Predictor"]
)

from services.predictor import (
    predictions,
    get_auth_token,
    get_iot_data,
    monitor_data
)

@router.get("/predict")
def predict():
   # For testing with IOT data, can only run on my computer for that part, normal prediction should work (getting from DB)
    # print("Authenticating...")
    # token = get_auth_token()
    # print(token)

    # print("Fetching data...")
    # data = get_iot_data(token)

    #For Testing 
    data = monitor_data()

    prediction = predictions()
    print(prediction)
    #Output is this like: [0.2596754215669358, 0.7615386158702746, 0.6457570238583724, 0.9308658648280802, 0.8079451844474845, 0.14271445010752157]
    # For ["Blow_Hole","Crack","Non_filling","Porosity","Shrinkage","Chipoff"]
    return {
        "blowhole": round(prediction[0] * 100, 2),
        "crack": round(prediction[1] * 100, 2),
        "non_filling": round(prediction[2] * 100, 2),
        "porosity": round(prediction[3] * 100, 2),
        "shrinkage": round(prediction[4] * 100, 2),
        "chipoff": round(prediction[5] * 100, 2),
    }

@router.get("/monitor")
def monitor():
    # print("Authenticating...")
    # token = get_auth_token()
    # print(token)

    # print("Fetching data...")
    # data = get_iot_data(token)

    data = monitor_data()
    #Output: {'cycletime value (sec)': 71.18, 'POURING TIME': 7.7, 'SHOT FWD TIME': 2.0, 
    # 'CURING TIME': 15.8, 'DIE OPEN CORE OUT TIME': 4.3, 'EJECTOR TIME': 5.6, 
    # 'EXTRACT TIME': 0.0, 'SPRAY TIME': 13.3, 'V1': 0.25, 'V2': 0.37, 'V3': 3.58, 
    # 'V4': 3.38, 'ACCEL. POINT': 356.0, 'DEACEL. POINT': 727.0, 'INTEN. TIME': 64.0, 'METAL PRESS.': 66.6, 
    # 'BISCUIT THICKNESS': 11.0, 'CLAMP FORCE': 0.0, 'CLAMP TONNAGE': 0.0, 'SHOT ACC. PRESSURE': 13.53, 
    # 'INTENSIFICATION ACC. PRESSURE': 13.81, 'FURNACE METAL TEMP.': 658.0}
    return data