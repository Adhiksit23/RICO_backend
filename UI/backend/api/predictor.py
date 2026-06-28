from fastapi import APIRouter

router = APIRouter(
    prefix="/api/predictor",
    tags=["Predictor"]
)

from services.predictor import (
    predictions,
    get_auth_token,
    get_iot_data
)

@router.get("/predict")
def predict():
    #For testing with IOT data, can only run on my computer for that part, normal prediction should work (getting from DB)
    # print("Authenticating...")
    # token = get_auth_token()
    # print(token)

    # print("Fetching data...")
    # data = get_iot_data(token)

    prediction = predictions()
    print(prediction)
    #Output is this: [0.2596754215669358, 0.7615386158702746, 0.6457570238583724, 0.9308658648280802, 0.8079451844474845, 0.14271445010752157]
    # For ["Blow_Hole","Crack","Non_filling","Porosity","Shrinkage","Chipoff"]
    return {
        "non_filling": 85.4,
        "blowhole": 9.2,
        "porosity": 47.4
    }