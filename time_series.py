import pandas as pd
import numpy as np
import datetime
import glob
import csv
import sys
from download_link import destination_folder_check


'''
Returns boolean signal so that smoothing is implemented
for business days instead of calendar days.
Compares amount of entries in dataframe after given date
with amount of roll_days.
'''
def is_current_date_past_roll_date(roll_days, dataframe, date_str):
    sliced_df = dataframe.loc[date_str:]
    row_amount = len(sliced_df.index) + 1
    signal = row_amount <= roll_days + 1
    return signal

'''
Comparing the input date with each contract's expiration date.
If the input date is past the contract's expiration +1 is added to the
valid_contract counter. If valid_contract == forward the first target contract
means we reached the desired month and are past the first_target_contract.
Returns the first contract to be used in the time series.
'''
def contract_finder(target_date, expiration_dates_list, months_forward):
    valid_contracts = 0
    for target_contract_index, a_contract in enumerate(expiration_dates_list):

        if  a_contract >= target_date:
            valid_contracts += 1
            print("VALID CONTRACTS " + str(valid_contracts))

            if valid_contracts == months_forward:
                break
    first_target_contract = expiration_dates_list[target_contract_index]

    return first_target_contract


'''
Creating a list with the available contracts, sorted by expiration date
and setting the index after the ones not needed before the target contract
so that the time series starts from the correct point in time.
'''
def contracts_to_list(csv_data_list, first_target_contract):
    date_list = []

    for index, a_file in enumerate(csv_data_list):
        temp_split_string = a_file.split('/',1)
        split_string = temp_split_string[1].split('.',1)
        date_list.append(split_string[0])

    try:
        target_index = date_list.index(first_target_contract)
    except ValueError:
        sys.exit('Invalid target contract index.')

    return target_index


'''
# target_date:      Time series' starting point. Input in '%Y-%m-%d' format.
# roll_days:        Amount of days ,before current contract expiration, roll to the next contract.
# months_forward:   Refers to the VX<forward>. Example: if forward=2 calculate VX2 curve.
# smoothing :       Toggle time-series smoothing starting on roll date using the perpetual series method.
'''
def generate_time_series(target_date, roll_days, months_forward, smoothing, expiration_dates_list):

    #Date format: Year-Month-Day
    date_format ='%Y-%m-%d'

    if roll_days > 15:
        sys.exit('Maximum roll days 15. Insert valid amount of days')

    data_path = "./Results"
    destination_folder_check(data_path)

    # Create new .json file where time series data will be inserted.
    if smoothing:
        file_name = data_path + '/' + target_date + '_' + str(roll_days) + '_' + str(months_forward) + '_Smoothed_' + '_Time_Series.json'
    else:
        file_name = data_path + '/' + target_date + '_' + str(roll_days) + '_' + str(months_forward) + '_Time_Series.json'

    '''
    Comparing the input date with each contract's expiration date.
    If the input date is past the contract's expiration +1 is added to the
    valid_contract counter. If valid_contract == forward the first target contract
    means we reached the desired month and are past the first_target_contract.
    '''
    first_target_contract = contract_finder(target_date, expiration_dates_list, months_forward)

    '''
    Creating a list with the available contracts, sorted by expiration date
    and setting the index after the ones not needed before the target contract
    so that the time series starts from the correct point in time.
    '''
    csv_data_list = sorted(glob.glob("data/*.csv"))

    target_index = contracts_to_list(csv_data_list, first_target_contract)

    # Create an empty df (data frame) with the files' column names.
    df = pd.DataFrame()
    next_df = pd.DataFrame()
    one_day = datetime.timedelta(days=1)
    parsed_roll_days = datetime.timedelta(days=roll_days)

    # Amount of weight shifted from the current contract to the next during rolls.
    if roll_days > 0:
        shift_weight = 1 / roll_days



#---------------------------------------------------------------------------------------------------------------------------------



    output_time_series = pd.DataFrame()
    parsed_last_used_date = ''
    # Goes through the file list and replaces the dataframe content each time a new file is accessed.
    counter = target_index

    while counter <= len(csv_data_list)-1:
        csv_file = csv_data_list[counter]
        df = pd.read_csv(csv_file)
        # print(df)


        split_string = csv_file.split("/",1)
        temp_name_list1 = split_string[1]
        temp_name_list2 = temp_name_list1.split('.',1)
        expiration_date = temp_name_list2[0]
        # print(expiration_date)

        weight_1 = 1
        weight_2    = 0

        roll = False

        while not roll:
            try:
                parsed_expiration_date = datetime.datetime.strptime(expiration_date, date_format)
            except ValueError:
                sys.exit("Can't parse date.")

            parsed_roll_date = parsed_expiration_date - parsed_roll_days

            if parsed_last_used_date == '':
                try:
                    parsed_last_used_date = datetime.datetime.strptime(target_date, date_format)
                except ValueError:
                    sys.exit("Can not parse date.")

            else:
                parsed_last_used_date = parsed_last_used_date + one_day


            date_indexed_df = df.set_index("Trade Date")

            # Emptying series so that previous data does not affect outcome.
            row = pd.Series([])
            next_row = pd.Series([])

            last_used_date_str = parsed_last_used_date.strftime(date_format)

            business_days_mode = is_current_date_past_roll_date(roll_days, date_indexed_df, last_used_date_str)

            # if smoothing and (parsed_last_used_date > parsed_roll_date) and business_days_mode:
            if smoothing and business_days_mode:
                print("SMOOTHING")

                weight_1 -= shift_weight
                weight_2    += shift_weight

                try:
                    row = date_indexed_df.loc[last_used_date_str]
                except KeyError:
                    # print("Not a business day.")
                    weight_1 += shift_weight
                    weight_2    -= shift_weight

                try:
                    # GET VALUES FROM THIS CONTRACT'S CURRENT DATE
                    current_contract_open = row.loc["Open"]
                    current_contract_high = row.loc["High"]
                    current_contract_low = row.loc["Low"]
                    current_contract_settle = row.loc["Settle"]
                    current_contract_volume = row.loc["Volume"]
                    current_contract_open_interest = row.loc["Open Interest"]

                    # GET VALUES FROM NEXT CONTRACT'S SAME DATE
                    next_csv_file = csv_data_list[counter+1]
                    next_df = pd.read_csv(next_csv_file)
                    next_date_indexed_df = next_df.set_index("Trade Date")
                    next_row = next_date_indexed_df.loc[last_used_date_str]

                    next_contract_open = next_row.loc["Open"]
                    next_contract_high = next_row.loc["High"]
                    next_contract_low = next_row.loc["Low"]
                    next_contract_settle = next_row.loc["Settle"]
                    next_contract_volume = next_row.loc["Volume"]
                    next_contract_open_interest = next_row.loc["Open Interest"]

                    #open, high, low, settle, volume, open interest

                    # DO THE MATH
                    new_open = (current_contract_open * weight_1) + (next_contract_open * weight_2)
                    new_high = (current_contract_high * weight_1) + (next_contract_high * weight_2)
                    new_low = (current_contract_low * weight_1) + (next_contract_low * weight_2)
                    new_settle = (current_contract_settle * weight_1) + (next_contract_settle * weight_2)
                    new_volume = (current_contract_volume * weight_1) + (next_contract_volume * weight_2)
                    new_open_interest = (current_contract_open_interest * weight_1) + (next_contract_open_interest * weight_2)

                    # SET ROW'S SETTLE TO NEW VALUE
                    row = row.replace({current_contract_open : new_open})
                    row = row.replace({current_contract_high : new_high})
                    row = row.replace({current_contract_low : new_low})
                    row = row.replace({current_contract_settle : new_settle})
                    row = row.replace({current_contract_volume : new_volume})
                    row = row.replace({current_contract_open_interest : new_open_interest})

                    # APPEND ROW
                    output_time_series = output_time_series.append(row)

                    # CONTINUE
                except KeyError:
                    # print(last_used_date_str + " IS NOT A BUSINESS DAY")
                    pass

            else:
                try:
                    row = date_indexed_df.loc[last_used_date_str]
                    output_time_series = output_time_series.append(row)
                except KeyError:
                    pass
                    # print("Not a business day.")


            roll_with_smoothing = (parsed_last_used_date == parsed_expiration_date) and smoothing
            roll_without_smoothing = (parsed_last_used_date == parsed_roll_date) and not smoothing

            if roll_with_smoothing or roll_without_smoothing:
                print("-----------ROLLING--------------")
                roll = True


        counter += 1
    print(output_time_series)
    output_time_series.to_json(file_name, index=True)
