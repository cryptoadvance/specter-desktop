Vue.component('qrencode',{
  template : '<div><qrcode v-bind:value="qrval" v-bind:options="wd"></qrcode></div>',
  data: function() {
     return {
        speed : 300,
        indx : 0,
        qrval : "",
        chunks : [],
        wd : { width: 400 }
     }
  },
  props: ['text', 'width'],
  created() {
    this.split()
    this.qrval=this.text
    this.wd = {width: this.width}
  },
  mounted() {this.init()},
  methods:{
    split : function() {
      var max_len = 300
      txt_len = this.text.length
      if (txt_len / max_len > 1.0) {
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
      this.indx++
      if (this.indx >= this.chunks.length) {
        this.indx = 0
      }
      this.qrval = this.chunks[this.indx]
    },
    init : function() {
      const self=this
      setInterval(self.animate, this.speed)
    }
  }
});
