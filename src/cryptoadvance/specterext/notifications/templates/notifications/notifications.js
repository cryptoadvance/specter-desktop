{% include "notifications/message_box.js" %}


var userToken = null;

/**
 * creating a notification from JS
 * 
 * Example:
 * createNotification('this is the title', {target_uis:['js_message_box', 'webapi'], body:'body line 1\nline 2', image:'/static/img/ghost_3d.png', timeout:3000})
 * 
 * Options dictionary can include:
        target_uis:  list of target_uis, e.g., ['js_message_box', 'webapi']    //  "default" will be replaced by default_target_ui
        notification_type: string,e.g. "information", all possibilities are: "debug", "information", "warning", "error", "exception"
        body: string
        data: any kind of data, which will be stored in the notification
        image: image url
        icon: currently only used for web_api (see https://notifications.spec.whatwg.org/#api ) , and not even on all platforms there
        timeout: [ms] after which the notification will close automatically. 
 */ 
 async function createNotification(title, options){ 
    if (!websocket){return}
    if (websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify( {'user_token': userToken, 'title':title, 'options': options}));
    } else {
        // If the socket is not open yet, retry in 1 s
        setTimeout(createNotification, 1000, title, options);  
    }
}



function onClose(id, targetUi){
    //console.log('closed message')    
    createNotification('on_close', {'target_uis':['internal_notification'], 'data':{'id':id, 'target_ui':targetUi}});
}


function onShow(id, targetUi, success=true){
    //console.log('closed message')
    createNotification('on_show', {'target_uis':['internal_notification'], 'data':{'id':id, 'target_ui':targetUi, 'success':success}});
}


function setTargetUiAvailability(targetUi, isAvailable, id=null) {
    createNotification('set_target_ui_availability', {'target_uis':['internal_notification'], 'data':{'id':id, 'target_ui':targetUi, 'is_available':isAvailable}});
}




var webapiHasPermission = false; //global variable           
/**
 * This function just checks if Notification_API is granted and writes the result
 * into the global variable webapiHasPermission.
 * webapiHasPermission has 3 states: true, false, "default"
 * true --> permission was given
 * false --> permission was denied
 * "default" --> no decision was made by the user
 * 
 * 
 * This function and the global variable is useful because then changes in 
 * Notification.permission can be detected.
 * 
 * @returns webapiHasPermission
 */
 function checkWebapiHasPermission(){
    if (!("Notification" in window)) {
        return false
    }
    // Let's check whether notification permissions have already been granted
    else if (Notification.permission === "granted") {
        webapiHasPermission = true;
    }  else if (Notification.permission === "denied") {
        webapiHasPermission = false;
    } else if (Notification.permission === "default") {
        // the user has not chosen anything, and the permission could be requested
        webapiHasPermission = "default";
    }

    return webapiHasPermission
}


/**
 * Checks and if necessary requests the Notification_API permission
 * @param {*} fGranted   A function that is called if fGranted == true
 * @param {*} fDenied    A function that is called if fGranted == false
 * @param {*} fDefault   A function that is called if fGranted == "default"
 * @param {*} retries_if_permission_default : How often should it request Notification_API permission?
 * @param {*} retry_time_distance : After how many milliseconds should it ask again for permission?
 * @returns webapiHasPermission
 */
function checkAndRequestWebapiPermission(fGranted, fDenied, fDefault, retries_if_permission_default=5, retry_time_distance=2000){
    if (!("Notification" in window)) {
        return false
    }
    // console.log(`checkAndRequestWebapiPermission ${retries_if_permission_default}`);
    checkWebapiHasPermission()

    if (webapiHasPermission == true) {
        fGranted();
    }  else if (webapiHasPermission == false) {
        fDenied();  
    } else // if the status is undecided, then request permission
    if (webapiHasPermission == "default") { 
        Notification.requestPermission().then(function (permission) {
        checkWebapiHasPermission();


        if (webapiHasPermission == true) {
            fGranted();
        }  else if (webapiHasPermission == false) {
            fDenied();  
        } else if (webapiHasPermission == "default") 
        // if the status is still undecided, then request permission after retry_time_distance (by recursion)
        if (webapiHasPermission == "default") { 
            // retry request permission through a recursive call:
            if (retries_if_permission_default>0){
                // create recursion loop, that breaks if user grants or blocks the notification
                // console.log(`Start recursion ${retries_if_permission_default-1}`);
                setTimeout(checkAndRequestWebapiPermission, retry_time_distance, fGranted, fDenied, fDefault, retries_if_permission_default-1, retry_time_distance);  
            } else
            // if it reached the end of the recursion without any user interaction, then
            // deactivate the ui_notification 
             if (retries_if_permission_default==0){
                fDefault();  
            }
        }
        });
    }
    return webapiHasPermission
}







/**
 * Created a Notifications_API notification similar to a push-notification.
 * It also asks for permission, if possible.
 * @param {*} jsNotification 
 * 
 * 
    In prinicple the jsNotification['options'] in can include all items listed in https://notifications.spec.whatwg.org/#api . 
    they are however not all used on all platforms, see https://developer.mozilla.org/en-US/docs/Web/API/notification#browser_compatibility

 * 
 */
function webapiNotification(jsNotification) {
    // console.log('webapiNotification')
    // https://developer.mozilla.org/en-US/docs/Web/API/Notifications_API/Using_the_Notifications_API
    var title = jsNotification['title'];
    var options = jsNotification['options'];

    function createWebapiNotification(){
        let notification = new Notification(title, options);
        // see https://flaviocopes.com/notifications-api/#add-an-image
        // see https://levelup.gitconnected.com/use-the-javascript-notification-api-to-display-native-popups-43f6227b9980
        // see https://www.htmlgoodies.com/html5/creating-your-own-notifications-with-the-html5-notifications-api/
        notification.onclick = (() => {
            // not implemented yet
        });        
        notification.onclose = (() => {
            onClose(jsNotification['id'], 'webapi');
        });        
        notification.onshow = (() => {
            // do something
            onShow(jsNotification['id'], 'webapi');
        });        

        function closeNotification(){notification.close()}
        if (jsNotification['timeout']>0) {
            setTimeout(closeNotification, jsNotification['timeout']);
        }
    };


    function fGranted(){
        createWebapiNotification();
    }
    function fDenied(){
        console.debug(`Notification.requestPermission() = ${webapiHasPermission}`);
        setTargetUiAvailability('webapi', false, jsNotification['id']);  
    }
    function fDefault(){
        console.debug(`Notification.requestPermission() = ${webapiHasPermission}`);
        setTargetUiAvailability('webapi', false, jsNotification['id']);  
    }

    checkAndRequestWebapiPermission(fGranted, fDenied, fDefault);
};




/**
 * Creates a javascript popup message.
 * 
 * @param {*} jsNotification 
 * 
 * Used options:
     - notification_type
     - body
     - image
     - timeout
 */
function jsMessageBox(jsNotification){
    function thisNotificationClose(){
        onClose(jsNotification['id'], 'js_message_box')            
    }

    var backgroundColor = null;
    if (jsNotification['notification_type']){
        backgroundColor = `var(--cmap-msgbox-${jsNotification['notification_type']})`
    }

    msgbox = new MessageBox({
        body: jsNotification['options']['body'],
        image: jsNotification['options']['image'],
        timeout: jsNotification['timeout'],
        closeLabel: 'Close',
        'onClose': thisNotificationClose,
        hideCloseButton: false,
        backgroundColor: backgroundColor,
      });
    msgbox.show(jsNotification['title']);			

    onShow(jsNotification['id'], 'js_message_box');
}


/**
 * Returns the full jsNotification in the javascript console 
 * @param {*} jsNotification 
 */
function js_console(jsNotification){
    if (jsNotification['notification_type'] == 'error'){
        console.error(jsNotification);
    } else if (jsNotification['notification_type'] == 'exception'){
        console.error(jsNotification);
    } else if (jsNotification['notification_type'] == 'warning'){
        console.warn(jsNotification);
    } else {            
        console.log(jsNotification);
    }
    onShow(jsNotification['id'], 'js_console');
    onClose(jsNotification['id'], 'js_console');
}


/**
 * Shows the jsNotification in the targetUi
 * @param {*} targetUi 
 * @param {*} jsNotification 
 * 
 * 
 * 
     jsNotification is the data structure usually created in python by notification.to_js_notification()
    An example jsNotification looks like:
        {
            "title": title,
            "id": id,
            "notification_type": notification_type,
            "timeout": timeout,
            "options": {
                body = "",
                image = None,
            },
        }
    
        In prinicple the options dict can include all items listed in https://notifications.spec.whatwg.org/#api . 
        - Only some of the are used in js_message_box (see jsMessageBox), 
            and even in web_api they are not all used on all platforms, see https://developer.mozilla.org/en-US/docs/Web/API/notification#browser_compatibility
        - js_logging will display the entire jsNotification data structure.

 */
async function show_notification(targetUi, jsNotification){
    if (targetUi == 'js_message_box'){
        jsMessageBox(jsNotification);
    } else if (targetUi == 'webapi'){
        webapiNotification(jsNotification);
    } else if (targetUi == 'js_console'){
        js_console(jsNotification);
    }

}



/**
 * Check the status of Notification_API permission call
 * setTargetUiAvailability to activate or deactivate the WebAPINotifications
 * This allows to activate the e.g. webapi again, if the user first denied it, and then allowed it again.
 */
async function sendUpdatedWebapiPermission(){
    var beforeWebapiHasPermission =  webapiHasPermission;
    var newWebapiHasPermission = checkWebapiHasPermission();

    // if something has changed
    if (beforeWebapiHasPermission != newWebapiHasPermission){


        // case: webapi was deactivated, but now is "granted"  
        if  ((newWebapiHasPermission == 'default')|| (newWebapiHasPermission == true)){
            setTargetUiAvailability('webapi', true);
            console.log('Activating webapi');
        }
        // case: webapi was active, but now is "denied" 
        else if   (newWebapiHasPermission == false) {
            setTargetUiAvailability('webapi', false);
            console.log('Deactivating webapi');            
        }

    }

}




var websocket = null;

function connectWebsocket() {
    // get necessary info for the opening of the websocket
    send_request("{{ url_for('notifications_endpoint.get_websockets_info') }}", 'GET', "{{ csrf_token() }}").then(function (websocketsInfo) {
        // Create the websocket  
        var url = "{{ url_for('notifications_endpoint.websocket') }}";
        console.log(url)
        userToken = websocketsInfo['user_token'];
        websocket = new WebSocket(url);

        // Authenticate and add listeners when the websocket connection is open
        websocket.onopen = function(e) {
            // Sends a message to the server, that does nothing, but enables the server to register the user_token to the websocket_client
            websocket.send(JSON.stringify({'user_token': userToken, "title": 'IGNORE_NOTIFICATION_TITLE'}));

            // set the api_permissions
            sendUpdatedWebapiPermission()
            setInterval(sendUpdatedWebapiPermission, 3000);
                
            console.debug(`Websocket connection to ${url} is open`);		
        };

        websocket.onmessage = function(message) {
            var jsNotification = null;
            try{ 
                jsNotification = JSON.parse(message.data);
            } catch(e) { 
                console.warn(`Json could not be parsed: ` + e.message)
                return
            }

            
            var targetUis = jsNotification["options"]['target_uis'];
            for (let i in targetUis) {  
                show_notification(targetUis[i], jsNotification);   
            }               
        };

        websocket.onclose = function(e) {
            console.debug('Websocket was closed. Reconnect will be attempted in 10 seconds.', e.reason);
            setTimeout(function() {
                connectWebsocket();
            }, 10000);
        };

        websocket.onerror = function(err) {
            console.error('Socket encountered error: ', err.message);
            // websocket.close();
        }; 
        
        
    })
    .catch(function (error) {
        console.error('Connection to the websocket failed. Reconnect will be attempted in 10 seconds.', error.reason);
        setTimeout(function() {
            connectWebsocket();
        }, 10000);
    });
      
}




/**
 * If a user is logged in then regularly check if the webapi notification permission was changed
 */
if ('{{ current_user.username }}'){
    connectWebsocket()
}else{
    // no user logged in
}