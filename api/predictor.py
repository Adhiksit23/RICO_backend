from fastapi import APIRouter

router = APIRouter(
    prefix="/api/predictor",
    tags=["Predictor"]
)

from services.predictor import (
    predictions,
    update_date_path,
    get_auth_token,
    get_iot_data,
    get_latest_calibration,
    last_predictions,
    monitor_data
)

@router.get("/predict")
def predict(die):
   # For testing with IOT data, can only run on my computer for that part, normal prediction should work (getting from DB)

    # print(ranges)
    #print(die)
    prediction = predictions(die)
    #print(prediction)
    #Output is this like: [0.2596754215669358, 0.7615386158702746, 0.6457570238583724, 0.9308658648280802, 0.8079451844474845, 0.14271445010752157]
    # For ["Blow_Hole","Crack","Non_filling","Porosity","Shrinkage","Chipoff"]
    last_predictions(die, 5)
    return {
        "blowhole": round(prediction[0] * 100, 2),
        "crack": round(prediction[1] * 100, 2),
        "non_filling": round(prediction[2] * 100, 2),
        "porosity": round(prediction[3] * 100, 2),
        "shrinkage": round(prediction[4] * 100, 2),
        "chipoff": round(prediction[5] * 100, 2),
    }

@router.get("/monitor")
def monitor(die):
    #print(die)
    data, die_id = monitor_data(die)
    #print(die_id)
    ranges = get_latest_calibration(die)
    #print([data, ranges])
    return [data, ranges]


@router.get("/update")
def update():
    # data_path = update_date_path()
    # print(data_path)
    
    # print("Authenticating...")
    # token = get_auth_token()
    # #print(token)

    # print("Fetching data...")
    # get_iot_data(token, data_path)
    # print("Recieved Data")
    return


@router.get("/last_pred")
def last_pred(die, N):
    last_predictions(die, N)
    return 