import json
from cryptoadvance.specter.util.fee_estimation import (
    FeeEstimationResult,
    FeeEstimationResultEncoder,
)


def test_FeeEstimationResultEncoder():

    fee_estimation = FeeEstimationResult(
        {
            "fastestFee": 1,
            "halfHourFee": 1,
            "hourFee": 1,
            "minimumFee": 1,
        }
    )
    fee_estimation.add_error_message("some error message ")
    fee_estimation.add_error_message("yet another one")
    my_json = json.dumps(fee_estimation, cls=FeeEstimationResultEncoder)
    my_dict = json.loads(my_json)
    assert my_dict["result"]["fastestFee"] == 1
    assert my_dict["error_messages"][1] == "yet another one"
