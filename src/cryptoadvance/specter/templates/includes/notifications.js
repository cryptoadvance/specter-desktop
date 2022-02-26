{% include "includes/utils.js" %}

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
        });
    }

    // At last, if the user has denied notifications, and you
    // want to be respectful there is no need to bother them any more.
};


current_chaintip_height = -1
function evalaute_new_transactions(){
    fetch("{{ url_for('wallets_endpoint_api.get_new_tx_notifications') }}")
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


    /*
    fetch("{{ url_for('wallets_endpoint_api.get_max_chaintip_height') }}")
        .then(function (response) {
            return response.json();
        }).then(function (max_chaintip_height) {
            // do something with the response
            if (current_chaintip_height == -1){
                current_chaintip_height = max_chaintip_height;
            }
            if (current_chaintip_height != max_chaintip_height){

                evalaute_new_transactions()
                notify_new_block(max_chaintip_height)
                current_chaintip_height = max_chaintip_height;
                //console.log(`new Block!!!  ${max_chaintip_height}`);
                // location.reload();
            } ;
        console.log(max_chaintip_height);
        });
        */
};


setInterval(run_scheduled, 2000);






