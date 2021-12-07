
SPRITE = 0
ORANGE_JUICE = 1


def make_drink_spritzer():

    # Update status and push to AWS


    # Make drink
    GPIO.setup(SPRITE, GPIO.OUT)
    GPIO.setup(ORANGE_JUICE, GPIO.OUT)

    GPIO.output(SPRITE, True)
    GPIO.output(ORANGE_JUICE, True)

    time.sleep(4)      

    GPIO.output(SPRITE, False)   
    GPIO.output(ORANGE_JUICE, False)

    # Update status and push to AWS

    print("Finished Drink")


def make_drink(drink):

    if drink == "Spritzer":
        make_drink_spritzer()
    elif drink == "Coke":
        make_drink_coke()
    elif drink == "Coke":
        make_drink_coke()        
    else:
        make_drink_coke()