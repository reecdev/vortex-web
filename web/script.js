const $ = function(e){return document.querySelector(e)};
const md = window.markdownit();
const socket = io();

function addChatMsg(role, content){
    let d = document.createElement("div");
    d.classList.add(role);
    d.textContent = content;
    $("#chat").append(d);
}

function rhash(length=64){
    const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
    const array = new Uint8Array(length);
    crypto.getRandomValues(array);

    return Array.from(array, (byte) => chars[byte % chars.length]).join("");
}

const chat_id = rhash();

let aresponse = "";
let didIntro = false;
let model_pref = "fast";

function doIntro(){
    $("#intro").remove();
    $("#chatbox").style.top = "auto";
    $("#chatbtn").style.top = "auto";
    $("#chatbox").style.bottom = "30px";
    $("#chatbtn").style.bottom = "38px";
    didIntro = true;
}

function chat(){
    let prompt = $("#chatbox").value;
    if(prompt.trim() !== ""){
        if(!didIntro){
            doIntro();
        }
        $("#chatbox").value = "";
        $("#chatbtn").disabled = "disabled";
        addChatMsg("user", prompt);
        socket.emit("user", {content: prompt, id: chat_id, model: model_pref});
        aresponse = "";
    }
}

$("#chatbox").addEventListener("keydown", function(e){
    if(e.key === "Enter"){
        chat();
    }
});

$("#chatbtn").addEventListener("click", function(){
    chat()
});

socket.on("assistant_newl", (data) => {
    addChatMsg("assistant", "");
});

socket.on("assistant", (data) => {
    aresponse = aresponse + data.toString();
    if(aresponse.trim() != ""){
        $("#chat").lastElementChild.innerHTML = md.render(aresponse);
        $("#chat").scrollTop = $("#chat").scrollHeight;
    }
});

socket.on("finw", (data) => {
    $("#chatbtn").removeAttribute("disabled");
});