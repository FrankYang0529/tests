*** Settings ***
Documentation        Simple example using SeleniumLibrary.
Resource             ../resources/login.robot
Suite Teardown       Close All Browsers


*** Test Cases ***
InValid Login
    [Setup]     Open Browser To Login Page
    [Teardown]  Screenshot And Close Window
    Given Input Username      something
          Input Password      not_correct
    And Submit Credentials
    Then Error Message Should Display

Valid Login
    [Setup]     Open Browser To Login Page
    [Teardown]  Screenshot And Close Window
    Given Open Browser To Login Page
          Input Username    ${HARVESTER_USERNAME}
          Input Password    ${HARVESTER_PASSWORD}
    And Submit Credentials
    Then Harvester Dashboard Should Be Display


*** Keywords ***
Input Username
    [Arguments]    ${username}
    Input Text      css:.labeled-input.edit > input[type='text']
    ...             ${username}

Input Password
    [Arguments]    ${password}
    Input Text      css:.labeled-input.edit > input[type='password']
    ...             ${password}

Submit Credentials
    Click Button    css:button[type=submit]

Screenshot And Close Window
    Run Keyword If Test Passed  Capture Page Screenshot
    Close Window


Error Message Should Display
    Wait Until Element Is Visible   css:div.login-messages .banner.error
    Element Should COntain          css:div.login-messages .banner.error
    ...                             Invalid username or password

Harvester Dashboard Should Be Display
    Wait Until Location Does Not Contain    auth/login
    ...                                     timeout=${BROWSER_WAIT_TIMEOUT}
    Location Should Contain     harvesterhci.io.dashboard
