{% include "includes/message_box.js" %}


/*  creating a notification from JS */
function createNotification(msg, timeout=3000, type="information", body=null, icon=null){
    url = "{{ url_for('wallets_endpoint_api.create_notification' ) }}";
	formData = new FormData();
	formData.append("title", msg)
	formData.append("timeout", timeout)
	formData.append("notification_type", type)
	formData.append("body", body)
	formData.append("icon", icon)
	send_request(url, 'POST', "{{ csrf_token() }}", formData)
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

function webpush_notification(js_notification) {
    // https://developer.mozilla.org/en-US/docs/Web/API/Notifications_API/Using_the_Notifications_API
    var title = js_notification['title'];
    var options = js_notification['options'];

    function show_notification(){
        let notification = new Notification(title, options);
    };


        if (!("Notification" in window)) {
        console.debug("This browser does not support desktop notification");
    }
    // Let's check whether notification permissions have already been granted
    else if (Notification.permission === "granted") {
        // If it's okay let's create a notification
        show_notification();
    }
    // Otherwise, we need to ask the user for permission
    else if (Notification.permission !== "denied") {
        Notification.requestPermission().then(function (permission) {
        // If the user accepts, let's create a notification
        if (permission === "granted") {
            show_notification();
        }        
        else{
         // not granted
        }
        });
    }


    

      
    // At last, if the user has denied notifications, and you
    // want to be respectful there is no need to bother them any more.
};




function callback_notification_close(id){
    //console.log('closed message')
    url = "{{ url_for('wallets_endpoint_api.js_notification_close', notification_id='this_notification_id') }}";
    send_request(url.replace('this_notification_id', id), 'GET', "{{ csrf_token() }}")
}

  
function javascript_popup_message(js_notification){


    function callback_notification_close_id(){
        callback_notification_close(js_notification['id'])    
    }

    const closeLabel = 'Close';
    msgboxPersistent.show(
        `${js_notification['title']}\n\n${js_notification['options']['body']}`,
        //() => {
        //  console.log("I am the callback! Of course, you may add various javaScript codes to make the callback function colourful.");
        //},
        callback_notification_close_id,
        closeLabel);			
}




async function get_new_notifications(){
    url = "{{ url_for('wallets_endpoint_api.get_new_notifications') }}"
    console.log(url)


    function myFunction(item) {
        sum += item;
    }

    send_request(url, 'GET', "{{ csrf_token() }}").then(function (js_notifications_dict) {
        console.log(js_notifications_dict)

        for (var web_notification_visualization in js_notifications_dict) {
            console.log("obj." + web_notification_visualization + " = " + js_notifications_dict[web_notification_visualization]);
            var js_notifications = js_notifications_dict[web_notification_visualization];
            for (let i in js_notifications) {                
                if (web_notification_visualization == 'js_message_box'){
                    javascript_popup_message(js_notifications[i]);
                } else if (web_notification_visualization == 'WebAPI'){
                    webpush_notification(js_notifications[i]);
                };
            }            
        }        
    });
}



async function run_scheduled(){ 
    //this code runs every interval  
  // createNotification('yes triggered notification')  // Triggering a nottification from JS works.
  get_new_notifications() ;
};



function test_notifications(){
    createNotification('debug title', timeout=4000,  type='debug', body='body\nbody', icon='/path/to/icon.png');
    createNotification('info title', timeout=4000, type='information',  body='body\nbody', icon='/path/to/icon.png');
    createNotification('warning title', timeout=4000, type='warning',  body='body\nbody', icon='/path/to/icon.png');
    createNotification('error title', timeout=4000, type='error',  body='body\nbody', icon='/path/to/icon.png');
}

setInterval(run_scheduled, 2000);






