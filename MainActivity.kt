package com.example.myapplication

import android.content.Context
import android.net.ConnectivityManager
import android.net.Uri
import androidx.appcompat.app.AppCompatActivity
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.Message
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import com.example.myapplication.databinding.ActivityMainBinding
import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject
import java.io.DataInputStream
import java.io.DataOutputStream
import java.net.Inet4Address
import java.net.NetworkInterface
import java.net.Socket
import kotlin.properties.Delegates
import org.videolan.libvlc.LibVLC
import org.videolan.libvlc.Media
import org.videolan.libvlc.MediaPlayer
import org.videolan.libvlc.util.VLCVideoLayout

class MainActivity : AppCompatActivity() {

    // 전역 변수로 바인딩 객체 선언
    private var mBinding: ActivityMainBinding? = null
    // 매번 null 체크를 할 필요 없이 편의성을 위해 바인딩 변수 재 선언
    private val binding get() = mBinding!! // getter brings out non-nullable object

    companion object{ // members callable by class name
        var socket = Socket() // create unconnected socket
        lateinit var writeSocket: DataOutputStream
        lateinit var readSocket: DataInputStream
        lateinit var cManager: ConnectivityManager
        lateinit var myIp: String
        private lateinit var libVlc: LibVLC
        private lateinit var mediaPlayer: MediaPlayer
        private lateinit var videoLayout: VLCVideoLayout

        var ip = "192.168.0.82"
        var port = 10000
        //var mHandler = Handler()      //-> API30부터 Deprecated됨. Looper를 직접 명시해야함
        var mHandler = Handler(Looper.getMainLooper())
        var serverClosed = true
    }

    /*
    private val resultLauncher = registerForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        playVideo(uri)
    }
    */

    // 버튼이 눌렸는지 확인
    private var pushedSensor = 0
    private var pushedHelp = 0
    private var pushedVideo = 0

    // 앱이 시작할 때 한 번 수행되어야 할 작업들 (setup)
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // 자동 생성된 뷰 바인딩 클래스에서의 inflate라는 메서드를 활용해서
        // 액티비티에서 사용할 바인딩 클래스의 인스턴스 생성
        mBinding = ActivityMainBinding.inflate(layoutInflater)

        //setContentView(R.layout.activity_main)
        setContentView(binding.root)

        // Monitor network connections
        cManager =
            applicationContext.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        socket.close() // close socket

        binding.buttonConnect.setOnClickListener {  //클라이언트 -> 서버 접속
            if(binding.etIp.text.isNotEmpty()) {
                ip = binding.etIp.text.toString()
                myIp = binding.etMyip.text.toString()
                if (binding.etPort.text.isNotEmpty()) {
                    port = binding.etPort.text.toString().toInt()
                    if (port < 0 || port > 65535)
                        toastShort("PORT 번호는 0부터 65535까지만 가능합니다.")
                    else if (!socket.isClosed)
                        toastShort("${ip}에 이미 연결되어 있습니다.")
                    else Connect().start()
                } else toastShort("PORT 번호를 입력해주세요.")
            } else toastShort("IP 주소를 입력해주세요.")
        }

        binding.buttonDisconnect.setOnClickListener {  //클라이언트 -> 서버 접속 끊기
            if(!socket.isClosed) {
                Disconnect().start()
                pushedSensor = 0
                pushedHelp = 0
                pushedVideo = 0
            }
            else toastShort("서버와 연결이 되어있지 않습니다.")
        }

        binding.buttonSend.setOnClickListener {    //상대에게 메시지 전송
            if(socket.isClosed) {
                toastShort("연결이 되어있지 않습니다.")
            } else {
                val mThread = SendMessage()
                mThread.setMsg(binding.etMsg.text.toString())
                mThread.start()
            }
        }

        binding.buttonSensor.setOnClickListener {    //센서 정보 수신
            if(socket.isClosed) {
                toastShort("연결이 되어있지 않습니다.")
            } else if (pushedSensor % 2 == 1) {
                val mThread = SensorMessage(true)
                mThread.start()
                pushedSensor += 1
            } else {
                val mThread = SensorMessage()
                mThread.start()
                pushedSensor += 1
            }
        }

        binding.buttonHelp.setOnClickListener {    //구조요청 (긴급메시지)
            if(socket.isClosed) {
                toastShort("연결이 되어있지 않습니다.")
            } else if (pushedHelp % 2 == 1) {
                toastShort("이미 구조요청을 전송했습니다.")
            } else {
                val mThread = HelpMessage()
                mThread.start()
                pushedHelp += 1
            }
        }

        libVlc = LibVLC(this)
        mediaPlayer = MediaPlayer(libVlc)

        binding.buttonVideo.setOnClickListener {    //동영상 수신
            if (pushedVideo % 2 == 1) {
                pushedVideo += 1
            } else {
                //resultLauncher.launch("video/*")
                var url: String = "rtsp://192.168.0.78:8080/"
                if (binding.etIp.text.isNotEmpty())
                    url = "rtsp://" + binding.etIp.text.toString() + ":8080/"
                playVideo(url)
                pushedVideo += 1
            }
        }

        mHandler = object : Handler(Looper.getMainLooper()){  //Thread들로부터 Handler를 통해 메시지를 수신
            override fun handleMessage(msg: Message) {
                super.handleMessage(msg)
                when(msg.what){
                    1-> toastShort("IP 주소가 잘못되었거나 서버의 포트가 개방되지 않았습니다.")
                    2->((binding.textStatus.text as String) + (msg.obj as String) + "\n").also { binding.textStatus.text = it }
                    3-> toastShort("서버에 접속하였습니다.")
                    4-> toastShort("메시지 전송에 실패하였습니다.")
                    5-> toastLong("인터넷이 연결되지 않았습니다. 연결 후 다시 시도하세요.")
                    6->{
                        binding.etMyip.setText(msg.obj as String)
                        myIp = msg.obj as String
                    }
                    7->{
                        val msg = JSONObject(msg.obj as String)
                        val obj: JSONObject = msg.getJSONObject("msg")
                        val gps: JSONArray = obj.getJSONArray("gps")
                        val lat = gps[0]
                        val lon = gps[1]
                        binding.sensorView.setText("Sat: GPS: [$lat, $lon]")
                    }
                }
            }
        }

        ShowInfo().start() //자신의 IP주소 확인
    }

    //클라이언트-서버 접속 시도
    class Connect:Thread(){

        override fun run() {
            try {
                socket = Socket(ip, port)
                writeSocket = DataOutputStream(socket.getOutputStream())
                readSocket = DataInputStream(socket.getInputStream())

                mHandler.obtainMessage(3).apply {
                    sendToTarget()
                }

                while (true) {
                    //서버로부터 메시지 수신 명령을 받았을 때
                    if (readSocket.available() != 0) {
                        val bac = readSocket.readUTF()
                        val input = bac.toString()
                        val recvInput = input.trim()
                        val msg = mHandler.obtainMessage()
                        if (recvInput[0] == '{') {
                            msg.what = 7
                        } else {
                            msg.what = 2
                        }
                        msg.obj = "$recvInput"
                        mHandler.sendMessage(msg)

                    }
                }
            } catch (e: Exception) {    //연결 실패
                val state = 1
                mHandler.obtainMessage(state).apply {
                    sendToTarget()
                }
                socket.close()
            }
        }
    }

    //클라이언트 접속 종료
    class Disconnect:Thread(){

        override fun run() {
            try{
                socket.close()
            }catch(e:Exception){

            }
        }
    }

    //메시지 전송
    class SendMessage:Thread(){
        private var state by Delegates.notNull<Int>()
        private lateinit var msg:String
        private lateinit var cname:String

        fun setMsg(m:String){
            msg = m
        }

        override fun run() {
            try {
                writeSocket.writeUTF(msg)    //메시지 내용
            } catch (e: Exception) {
                e.printStackTrace()
                mHandler.obtainMessage(4).apply {
                    sendToTarget()
                }
            }
        }
    }

    //센서메시지 전송
    class SensorMessage(var stopflag: Boolean = false):Thread(){
        private lateinit var msg:String

        fun setJSON():JSONObject {
            val obj = JSONObject()
            val msgobj = JSONObject()
            val jsonarray = JSONArray()
            val gps = listOf(35.0, 129.0) // gps coordinate of mobile
            try{
                msgobj.put("sender","mobile")
                msgobj.put("receiver","rpi1")
                msgobj.put("sensor",(if(stopflag) "false" else "true"))
                for (i in 0 until gps.size) {
                    jsonarray.put(gps.get(i))
                }
                msgobj.put("gps", jsonarray)
                obj.put("msg",msgobj)

            } catch(e: JSONException) {
                e.printStackTrace()
            }
            return obj
        }

        override fun run() {
            try {
                writeSocket.writeUTF(setJSON().toString())    //메시지 내용
            } catch (e: Exception) {
                e.printStackTrace()
                mHandler.obtainMessage(4).apply {
                    sendToTarget()
                }
            }
        }
    }

    //긴급메시지 전송 (GPS 정보 포함)
    class HelpMessage(var stopflag: Boolean = false):Thread(){
        private lateinit var msg:String

        fun setJSON():JSONObject {
            val obj = JSONObject()
            val msgobj = JSONObject()
            val jsonarray = JSONArray()
            val gps = listOf(35.0, 129.0) // gps coordinate of mobile
            try{
                msgobj.put("sender","mobile")
                msgobj.put("receiver","rpi1")
                msgobj.put("help","true")
                for (i in 0 until gps.size) {
                    jsonarray.put(gps.get(i))
                }
                msgobj.put("gps", jsonarray)
                obj.put("msg",msgobj)

            }catch(e: JSONException){
                e.printStackTrace()
            }
            return obj
        }

        override fun run() {
            try {
                writeSocket.writeUTF(setJSON().toString())    //메시지 내용
            } catch (e: Exception) {
                e.printStackTrace()
                mHandler.obtainMessage(4).apply {
                    sendToTarget()
                }
            }
        }
    }

    //자신의 IP주소를 표시
    class ShowInfo:Thread() {

        override fun run() {
            var ip = ""
            val en = NetworkInterface.getNetworkInterfaces()
            while (en.hasMoreElements()) {
                val intf = en.nextElement()
                val enumIpAddr = intf.inetAddresses
                while (enumIpAddr.hasMoreElements()) {
                    val inetAddress = enumIpAddr.nextElement()
                    if (!inetAddress.isLoopbackAddress && inetAddress is Inet4Address) {
                        @Suppress("RECEIVER_NULLABILITY_MISMATCH_BASED_ON_JAVA_ANNOTATIONS")
                        Companion.ip = inetAddress.hostAddress as String
                    }
                }
            }

            if (ip == "") {
                mHandler.obtainMessage(5).apply {
                    sendToTarget()
                }
            } else {
                val msg = mHandler.obtainMessage()
                msg.what = 6
                msg.obj = Companion.ip
                mHandler.sendMessage(msg)
            }
        }
    }

    override fun onStop()
    {
        super.onStop()

        mediaPlayer.stop()
        mediaPlayer.detachViews()
    }

    override fun onDestroy()
    {
        super.onDestroy()

        mediaPlayer.release()
        libVlc.release()
    }

    private fun playVideo(url: String?)
    {
        /*
        if (uri === null) {
            return
        }
        val fd = contentResolver.openFileDescriptor(uri, "r")
         */

        mediaPlayer.attachViews(binding.videoLayout, null, false, false)

        val media = Media(libVlc, Uri.parse(url))
        media.setHWDecoderEnabled(true, false)
        media.addOption(":network-caching=600")

        mediaPlayer.media = media
        media.release()
        mediaPlayer.play()
    }

    // 화면에 잠시 띄우는 메시지
    private fun toastShort(message: String) {
        Toast.makeText(this@MainActivity, message, Toast.LENGTH_SHORT).show()
    }

    // 화면에 잠시 띄우는 메시지 (조금 더 길게)
    private fun toastLong(message: String) {
        Toast.makeText(this@MainActivity, message, Toast.LENGTH_LONG).show()
    }

}