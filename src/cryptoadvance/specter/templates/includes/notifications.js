{% include "includes/message_box.js" %}




/*  creating a notification from JS */
async function requestCreateNotification(title, options){ 
    var url = "{{ url_for('wallets_endpoint_api.create_notification' ) }}";
	var formData = new FormData();
	formData.append("title", title)
    formData.append('options', JSON.stringify( options));
    return send_request(url, 'POST', "{{ csrf_token() }}", formData)
}




function on_close(id, target_ui){
    //console.log('closed message')
    requestCreateNotification('on_close', {target_uis:['internal_notification'], data:{'id':id, 'target_ui':target_ui}});
}


function on_show(id, target_ui, success=true){
    //console.log('closed message')
    requestCreateNotification('on_show', {target_uis:['internal_notification'], data:{'id':id, 'target_ui':target_ui, 'success':success}});
}


function notification_deactivate_target_ui_and_rebroadcast(id, target_ui) {
    requestCreateNotification('notification_deactivate_target_ui_and_rebroadcast', {target_uis:['internal_notification'], data:{'id':id, 'target_ui':target_ui}});
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



function webapi_notification(js_notification, retries_if_permission_default=2) {
    console.log('webapi_notification')
    // https://developer.mozilla.org/en-US/docs/Web/API/Notifications_API/Using_the_Notifications_API
    var title = js_notification['title'];
    var options = js_notification['options'];

    function create_webapi_notification(){
        let notification = new Notification(title, options);
        // see https://flaviocopes.com/notifications-api/#add-an-image
        // see https://levelup.gitconnected.com/use-the-javascript-notification-api-to-display-native-popups-43f6227b9980
        // see https://www.htmlgoodies.com/html5/creating-your-own-notifications-with-the-html5-notifications-api/
        notification.onclick = (() => {
            // do something
        });        
        notification.onclose = (() => {
            on_close(js_notification['id'], 'WebAPI')
        });        
        notification.onshow = (() => {
            // do something
            on_show(js_notification['id'], 'WebAPI')
        });        

        function closeNotification(){notification.close()}
        if (js_notification['timeout']>0) {
            setTimeout(closeNotification, js_notification['timeout']);
        }
    };


    if (!("Notification" in window)) {
        console.log("This browser does not support desktop notification");
        notification_deactivate_target_ui_and_rebroadcast(js_notification['id'], 'WebAPI');
    }
    // Let's check whether notification permissions have already been granted
    else if (Notification.permission === "granted") {
        // If it's okay let's create a notification
        create_webapi_notification();
    }  else if (Notification.permission === "denied") {
        // If it's okay let's create a notification
        console.log(`Notification.requestPermission() = ${Notification.permission}`);
        notification_deactivate_target_ui_and_rebroadcast(js_notification['id'], 'WebAPI');  
    }
    // Otherwise  "default", we need to ask the user for permission
    else   {
        Notification.requestPermission().then(function (permission) {
        // If the user accepts, let's create a notification
        if (permission === "granted") {
            create_webapi_notification();
        } else if (permission === "denied") {
            // not granted
            console.log(`Notification.requestPermission() = ${permission}`);
            notification_deactivate_target_ui_and_rebroadcast(js_notification['id'], 'WebAPI');  
        } else {
            // permission is probably "default", meaning the user has neither granted nor blocked the Notifications.
            // The user can afterwards allow or block notifications.  The notification needs reboradcasting.
            console.log(`Notification.requestPermission() = ${permission}`);
            if (retries_if_permission_default>0){
                // create recursion loop, that breaks if user grants or blocks the notification
                setTimeout(webapi_notification, 2000, js_notification, retries_if_permission_default=retries_if_permission_default-1);  
            }
        }
        });
    }


    

      
    // At last, if the user has denied notifications, and you
    // want to be respectful there is no need to bother them any more.
};




  
function js_message_box(js_notification){
    function this_notification_close(){
        on_close(js_notification['id'], 'js_message_box')    
    }

    var message = js_notification['title'];
    if (js_notification['options']['body']) {
        message += '\n\n' + js_notification['options']['body']
    }

    msgbox = new MessageBox({
        closeTime: js_notification['timeout']
      });
    msgbox.show(
        message,
        this_notification_close,
        'Close',
        image=js_notification['options']['image'],
        );			

    on_show(js_notification['id'], 'js_message_box')
}


function js_console(js_notification){
    if (js_notification['notification_type'] == 'error'){
        console.error(js_notification)
    } else if (js_notification['notification_type'] == 'exception'){
        console.error(js_notification)
    } else if (js_notification['notification_type'] == 'warning'){
        console.warn(js_notification)
    } else {            
        console.log(js_notification);
    }
    on_show(js_notification['id'], 'js_console')
}

async function show_notification(ui_name, js_notification){
    if (ui_name == 'js_message_box'){
        js_message_box(js_notification);
    } else if (ui_name == 'WebAPI'){
        webapi_notification(js_notification);
    } else if (ui_name == 'js_console'){
        js_console(js_notification);
    }

}


async function get_new_notifications(){
    url = "{{ url_for('wallets_endpoint_api.get_new_notifications') }}"
    //console.log(url)


    function myFunction(item) {
        sum += item;
    }

    send_request(url, 'GET', "{{ csrf_token() }}").then(function (js_notifications_dict) {
            //console.log(js_notifications_dict);
            for (var ui_name in js_notifications_dict) {
            //console.log("obj." + ui_name + " = " + js_notifications_dict[ui_name]);
            for (let i in js_notifications_dict[ui_name]) {  
                show_notification(ui_name, js_notifications_dict[ui_name][i])  ;   
            }            
        }        
    });
}



async function run_scheduled(){ 
    //this code runs every interval  
  // requestCreateNotification('yes triggered notification')  // Triggering a nottification from JS works.
  if ('{{ current_user.username }}'){
    console.log('{{ current_user.username }}')
    get_new_notifications() ;  
  }else{
    // no user logged in
  }
};



setInterval(run_scheduled, 2000);






