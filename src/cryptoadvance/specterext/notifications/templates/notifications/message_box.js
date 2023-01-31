// see https://coder-question.com/cq-blog/525543  and https://dev.to/takaneichinose/responsive-message-box-with-javascript-class-25ie
class MessageBox {
  constructor(option) {
    this.option = option;
    
    this.msgBoxArea = document.querySelector("#msgbox-area");
    
    if (this.msgBoxArea === null) {
      this.msgBoxArea = document.createElement("DIV");
      this.msgBoxArea.setAttribute("id", "msgbox-area");
      this.msgBoxArea.classList.add("msgbox-area");
      
      document.body.appendChild(this.msgBoxArea);
    }
  }
  
  show(title) {
    if (title === "" || title === undefined || title === null) { 
      throw "title is empty or not defined.";
    }
    

    const msgboxBox = document.createElement("DIV");
    const msgboxImage = document.createElement("DIV");
    const msgboxContent = document.createElement("DIV");
    const msgboxTextWrapper = document.createElement("DIV");
    const msgboxTitle = document.createElement("DIV");
    const msgboxText = document.createElement("DIV");
    const msgboxCommand = document.createElement("DIV");
    const msgboxClose = document.createElement("A");
    
  
    if (this.option.image != null){
      msgboxImage.classList.add("msgbox-img");
      var img = document.createElement("img");
      img.width = 100;
      img.src = this.option.image;
      msgboxImage.width = '100px';
      msgboxImage.appendChild(img);
      msgboxContent.appendChild(msgboxImage);
    }

    // Content area of the message box
    msgboxContent.classList.add("msgbox-content");

    // title and text div
    msgboxTextWrapper.classList.add("msgbox-wrapper");
    msgboxContent.appendChild(msgboxTextWrapper);

    //  title 
    msgboxTitle.classList.add("msgbox-title");
    msgboxTitle.setAttribute('style', 'font-weight: bold; margin-bottom:8px;');    
    msgboxTitle.innerText = title;
    msgboxTextWrapper.appendChild(msgboxTitle);

    // Text area
    if (this.option.body != null){
      msgboxText.classList.add("msgbox-text");
      msgboxText.innerText = this.option.body;
      msgboxTextWrapper.appendChild(msgboxText);
    }
        
    // Command box or the button container
    msgboxCommand.classList.add("msgbox-command");
    
    // Close button of the message box
    msgboxClose.classList.add("msgbox-close");
    msgboxClose.setAttribute("href", "#");
    if (this.option.closeLabel === undefined || this.option.closeLabel === null) {
      this.option.closeLabel = "Close";
    }        
    msgboxClose.innerText = this.option.closeLabel;
    
    // Container of the Message Box element
    msgboxBox.classList.add("msgbox-box");
    if (this.option.backgroundColor){
      msgboxBox.style.backgroundColor = this.option.backgroundColor;
    }
    msgboxBox.setAttribute("timeout", this.option.timeout);
    msgboxBox.appendChild(msgboxContent);

    if (this.option.hideCloseButton === false
        || this.option.hideCloseButton === undefined) {
      // If the hideCloseButton flag is false, or if it is undefined
      
      // Append the close button to the container
      msgboxCommand.appendChild(msgboxClose);
      msgboxBox.appendChild(msgboxCommand);
    }

    this.msgBoxArea.appendChild(msgboxBox);
    
    msgboxClose.onclick = (evt) => {
      evt.preventDefault();
      
      if (msgboxBox.classList.contains("msgbox-box-hide")) {
        return;
      }
      
      clearTimeout(this.msgboxTimeout);
      
      this.msgboxTimeout = null;

      this.hide(msgboxBox, this.option.onClose);
    };

    if (this.option.timeout > 0) {
      this.msgboxTimeout = setTimeout(() => {
        this.hide(msgboxBox, this.option.onClose);
      }, this.option.timeout);
    }
  }
  
  hideMessageBox(msgboxBox) {
    return new Promise(resolve => {
      msgboxBox.ontransitionend = () => {
        resolve();
      };
    });
  }
  
  async hide(msgboxBox, callback) {
    if (msgboxBox !== null) {
      // If the Message Box is not yet closed
      
      msgboxBox.classList.add("msgbox-box-hide");
    }
    
    await this.hideMessageBox(msgboxBox);
    
    this.msgBoxArea.removeChild(msgboxBox);

    clearTimeout(this.msgboxTimeout);
    
    if (typeof callback === "function") {
      // If the callback parameter is a function

      callback();
    }
  }
}

const msgboxShowMessage = document.querySelector("#msgboxShowMessage");
const msgboxHiddenClose = document.querySelector("#msgboxHiddenClose");

// Creation of Message Box class, and the sample usage
/*
const msgbox = new MessageBox({
  timeout: 10000,
  hideCloseButton: false
});
const msgboxPersistent = new MessageBox({
  timeout: 0
});
const msgboxNoClose = new MessageBox({
  timeout: 5000,
  hideCloseButton: true
});


*/