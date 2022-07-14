{% include "includes/message_box.js" %}




/**
 * creating a notification from JS
 * 
 * Example:
 * CreateNotification('this is the title', {target_uis:['js_message_box', 'WebAPI'], body:'body line 1\nline 2', image:'/static/img/ghost_3d.png', timeout:3000})
 */ 
 async function CreateNotification(title, options){ 
    if (websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify( {'title':title, 'options': options}));
    } else {
        // If the socket is not open yet, retry in 1 s
        setTimeout(CreateNotification, 1000, title, options);  
    }
}



function on_close(id, target_ui){
    //console.log('closed message')    
    CreateNotification('on_close', {target_uis:['internal_notification'], data:{'id':id, 'target_ui':target_ui}});
}


function on_show(id, target_ui, success=true){
    //console.log('closed message')
    CreateNotification('on_show', {target_uis:['internal_notification'], data:{'id':id, 'target_ui':target_ui, 'success':success}});
}


function set_target_ui_availability(target_ui, is_available, id=null) {
    CreateNotification('set_target_ui_availability', {target_uis:['internal_notification'], data:{'id':id, 'target_ui':target_ui, 'is_available':is_available}});
}




    /* js_notification structure see https://notifications.spec.whatwg.org/#api
    options : {  
        "//": "Visual Options",
        "body": "<String>",
        "icon": "<URL String>",
        "image": "<URL String>",
        "badge": "<URL String>",
        "vibrate": "<Array of Integers>",
        "sound": "<URL String>",
        "dir": "<String of 'auto' | 'ltr' | 'rtl'>",
    
        "//": "Behavioral Options",
        "tag": "<String>",
        "data": "<Anything>",
        "requireInteraction": "<boolean>",
        "renotify": "<Boolean>",
        "silent": "<Boolean>",
    
        "//": "Both visual & behavioral options",
        "actions": "<Array of Strings>",
    
        "//": "Information Option. No visual affect.",
        "timestamp": "<Long>"
    }
    */



var webapi_has_permission = false; //global variable           
/**
 * This function just checks if Notification_API is granted and writes the result
 * into the global vriable webapi_has_permission.
 * webapi_has_permission has 3 states: true, false, "default"
 * true --> permission was given
 * false --> permission was denied
 * "default" --> no decision was made by the user
 * 
 * 
 * This function and the global variable is useful because then changes in 
 * Notification.permission can be detected.
 * 
 * @returns webapi_has_permission
 */
 function check_webapi_has_permission(){
    if (!("Notification" in window)) {
        return false
    }
    // Let's check whether notification permissions have already been granted
    else if (Notification.permission === "granted") {
        webapi_has_permission = true;
    }  else if (Notification.permission === "denied") {
        webapi_has_permission = false;
    } else if (Notification.permission === "default") {
        // the user has not chosen anything, and the permission could be requested
        webapi_has_permission = "default";
    }

    return webapi_has_permission
}


/**
 * Checks and if necessary requests the Notification_API permission
 * @param {*} f_granted   A function that is called if f_granted == true
 * @param {*} f_denied    A function that is called if f_granted == false
 * @param {*} f_default   A function that is called if f_granted == "default"
 * @param {*} retries_if_permission_default : How often should it request Notification_API permission?
 * @param {*} retry_time_distance : After how many milliseconds should it ask again for permission?
 * @returns webapi_has_permission
 */
function check_and_request_webapi_permission(f_granted, f_denied, f_default, retries_if_permission_default=5, retry_time_distance=2000){
    if (!("Notification" in window)) {
        return false
    }
    // console.log(`check_and_request_webapi_permission ${retries_if_permission_default}`);
    check_webapi_has_permission()

    if (webapi_has_permission == true) {
        f_granted();
    }  else if (webapi_has_permission == false) {
        f_denied();  
    } else // if the status is undecided, then request permission
    if (webapi_has_permission == "default") { 
        Notification.requestPermission().then(function (permission) {
        check_webapi_has_permission();


        if (webapi_has_permission == true) {
            f_granted();
        }  else if (webapi_has_permission == false) {
            f_denied();  
        } else if (webapi_has_permission == "default") 
        // if the status is still undecided, then request permission after retry_time_distance (by recursion)
        if (webapi_has_permission == "default") { 
            // retry request permission through a recursive call:
            if (retries_if_permission_default>0){
                // create recursion loop, that breaks if user grants or blocks the notification
                // console.log(`Start recursion ${retries_if_permission_default-1}`);
                setTimeout(check_and_request_webapi_permission, retry_time_distance, f_granted, f_denied, f_default, retries_if_permission_default-1, retry_time_distance);  
            } else
            // if it reached the end of the recursion without any user interaction, then
            // deactivate the ui_notification 
             if (retries_if_permission_default==0){
                f_default();  
            }
        }
        });
    }
    return webapi_has_permission
}



/**
 * Created a Notifications_API notification similar to a push-notification.
 * It also asks for permission, if possible.
 * @param {*} js_notification 
 */
function webapi_notification(js_notification) {
    // console.log('webapi_notification')
    // https://developer.mozilla.org/en-US/docs/Web/API/Notifications_API/Using_the_Notifications_API
    var title = js_notification['title'];
    var options = js_notification['options'];

    function create_webapi_notification(){
        let notification = new Notification(title, options);
        // see https://flaviocopes.com/notifications-api/#add-an-image
        // see https://levelup.gitconnected.com/use-the-javascript-notification-api-to-display-native-popups-43f6227b9980
        // see https://www.htmlgoodies.com/html5/creating-your-own-notifications-with-the-html5-notifications-api/
        notification.onclick = (() => {
            // not implemented yet
        });        
        notification.onclose = (() => {
            on_close(js_notification['id'], 'WebAPI');
        });        
        notification.onshow = (() => {
            // do something
            on_show(js_notification['id'], 'WebAPI');
        });        

        function closeNotification(){notification.close()}
        if (js_notification['timeout']>0) {
            setTimeout(closeNotification, js_notification['timeout']);
        }
    };


    function f_granted(){
        create_webapi_notification();
    }
    function f_denied(){
        console.log(`Notification.requestPermission() = ${webapi_has_permission}`);
        set_target_ui_availability('WebAPI', false, js_notification['id']);  
    }
    function f_default(){
        console.log(`Notification.requestPermission() = ${webapi_has_permission}`);
        set_target_ui_availability('WebAPI', false, js_notification['id']);  
    }

    check_and_request_webapi_permission(f_granted, f_denied, f_default);
};




/**
 * Creates a javascript popup message.
 * @param {*} js_notification 
 */
function js_message_box(js_notification){
    function this_notification_close(){
        on_close(js_notification['id'], 'js_message_box')    
    }
 
    msgbox = new MessageBox({
        closeTime: js_notification['timeout']
      });
    msgbox.show(
        js_notification['title'], 
        js_notification['options']['body'],
        this_notification_close,
        'Close',
        image=js_notification['options']['image'],
        );			

    on_show(js_notification['id'], 'js_message_box');
}


/**
 * Returns the full js_notification in the javascript console 
 * @param {*} js_notification 
 */
function js_console(js_notification){
    if (js_notification['notification_type'] == 'error'){
        console.error(js_notification);
    } else if (js_notification['notification_type'] == 'exception'){
        console.error(js_notification);
    } else if (js_notification['notification_type'] == 'warning'){
        console.warn(js_notification);
    } else {            
        console.log(js_notification);
    }
    on_show(js_notification['id'], 'js_console');
    on_close(js_notification['id'], 'js_console');
}


/**
 * Shows the js_notification in the target_ui
 * @param {*} target_ui 
 * @param {*} js_notification 
 */
async function show_notification(target_ui, js_notification){
    if (target_ui == 'js_message_box'){
        js_message_box(js_notification);
    } else if (target_ui == 'WebAPI'){
        webapi_notification(js_notification);
    } else if (target_ui == 'js_console'){
        js_console(js_notification);
    }

}



/**
 * Check the status of Notification_API permission call
 * set_target_ui_availability to activate or deactivate the WebAPINotifications
 */
async function send_updated_webapi_permission(){
    var before_webapi_has_permission =  webapi_has_permission;
    var new_webapi_has_permission = check_webapi_has_permission();

    // if something has changed
    if (before_webapi_has_permission != new_webapi_has_permission){


        // case: webapi was deactivated, but now is "granted"  
        if  ((new_webapi_has_permission == 'default')|| (new_webapi_has_permission == true)){
            set_target_ui_availability('WebAPI', true);
            console.log('Activating WebAPI');
        }
        // case: webapi was active, but now is "denied" 
        else if   (new_webapi_has_permission == false) {
            set_target_ui_availability('WebAPI', false);
            console.log('Deactivating WebAPI');            
        }

    }

}




var  websocket = null;

function connect_and_authenticate_websocket(){
    // get necessary info for the opening of the websocket
    send_request("{{ url_for('wallets_endpoint_api.get_websockets_info') }}", 'GET', 
                    "{{ csrf_token() }}").then(function (websockets_info) {
        // Create the websocket  
        var port = websockets_info['port'];
        var user_token = websockets_info['user_token'];

        ip_address = "{{ request.host.split(':')[0] }}";
        websocket = new WebSocket(`ws://${ip_address}:${port}/`);


        

        // Authenticate and add listeners when the websocket connection is open
        websocket.onopen = function(e) {
            websocket.send(JSON.stringify( {'type':'authentication', 'user_token': websockets_info['user_token']}));
            console.log(`websocket connection open and authenticated`);		
            //websocket.send(JSON.stringify( {'title':'This message is sent to the server and then returned', options: {target_uis:['js_console']}  }));
        };

        websocket.onmessage = function(message) {
            var js_notification = JSON.parse(message.data);
            var target_uis = js_notification["options"]['target_uis'];
            for (let i in target_uis) {  
                show_notification(target_uis[i], js_notification);   
            }               
        };

        websocket.onclose = function(e) {
            console.log('Websocket was closed. Reconnect will be attempted in 10 second.', e.reason);
            setTimeout(function() {
                connect_and_authenticate_websocket();
            }, 10000);
        };

        websocket.onerror = function(err) {
            console.error('Socket encountered error: ', err.message);
            // websocket.close();
        };    

    });		

    



}

connect_and_authenticate_websocket()





/**
 * If a user is logged in then regularrly check the WebAPI notification permission
 */
 if ('{{ current_user.username }}'){
    setInterval(send_updated_webapi_permission, 3000);
}else{
    // no user logged in
}
