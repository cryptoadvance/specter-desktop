Vue.component('qrencode',{
  template : '<div :title="title" v-on:click="clicked()"><qrcode :value="qrval" :options="wd"></qrcode></div>',
  data: function() {
     return {
        speed : 300,
        indx : 0,
        qrval : "",
        chunks : [],
        title : "",
        isQRlarge : false,
        isQRplaying : false,
        wd : { width: 400 }
     }
  },
  props: ['text', 'width'],
  created() {
    this.split()
    this.qrval=this.text
    this.wd = {width: this.width}
    if (this.isQRlarge) {this.title = "Click to animate!"}
  },
  mounted() {this.init()},
  methods:{
    split : function() {
      var max_len = 300
      txt_len = this.text.length
      if (txt_len / max_len > 1.0) {
        this.isQRlarge = true
        let number_of_chunks = Math.ceil(txt_len / max_len)
        n = Math.ceil(txt_len / number_of_chunks)
        for (let i = 0; i < txt_len; i += n) {
          this.chunks.push(this.text.substring(i, i + n));
        }
        for (let j=0; j<this.chunks.length; j++) {
          this.chunks[j] = "p"+(j+1)+"of"+number_of_chunks+" "+this.chunks[j]
        }
      }
      else {
        this.chunks.push(this.text)
      }
    },
    animate : function() {
      if (this.isQRplaying == false) {
        this.qrval = this.text
        this.title = "Click to animate!"
      }
      else {
        this.indx++
        if (this.indx >= this.chunks.length) {this.indx = 0}
        this.qrval = this.chunks[this.indx]
        this.title = "Click to stop animation!"
      }
      if (!this.isQRlarge) {
        this.title = ""
      }
    },
    init : function() {
      const self=this
      setInterval(self.animate, this.speed)
    },
    clicked : function() {
      this.isQRplaying = !this.isQRplaying
    }
  }
});
