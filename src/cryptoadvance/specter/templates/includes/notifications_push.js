

{% include "includes/utils.js" %}
{% include "includes/message_box.js" %}


function javascript_popup_message(title, options){

    msgboxPersistent.show(
        `${title}\n\n${options['body']}`,
        //() => {
        //  console.log("I am the callback! Of course, you may add various javaScript codes to make the callback function colourful.");
        //},
        //"Has callback"
      );			
}

function webpush_notification(title, options) {
    function show_notification(){
        let notification = new Notification(title, options);
    };

    /*
{
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
    //document.title = `1 new notification: ${title}`;

    // Let's check if the browser supports notifications    
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
            javascript_popup_message(title, options)
        }
        });
    }


    

      
    // At last, if the user has denied notifications, and you
    // want to be respectful there is no need to bother them any more.
};


current_chaintip_height = -1
function evalaute_new_transactions(){
    fetch("{{ url_for('wallets_endpoint_api.get_new_notifications') }}")
        .then(function (response) {
            return response.json();
        }).then(function (tx_notifications) {
            // do something with the response
            console.log(tx_notifications)
            for (let i in tx_notifications) {
                console.log(tx_notifications[i]);
                tx_notifications[i]['icon'] = getCategoryImg(tx_notifications[i]['category'], tx_notifications[i]['isConfirmed']);  // TODO: Doesnt work
                tx_notifications[i]['image'] = tx_notifications[i]['icon']
                tx_notifications[i]['badge'] = tx_notifications[i]['icon']                                
                webpush_notification(tx_notifications[i]['title'], tx_notifications[i]['options']);
            }

        });
};

function notify_new_block(max_chaintip_height){
    //webpush_notification(`New Block ${max_chaintip_height}`)
};

function run_scheduled(){ 
    //this code runs every interval  
  evalaute_new_transactions() 
};


setInterval(run_scheduled, 2000);






