//input 태그 선택자로 선택
let inputTag = document.querySelector(".copy-value");
        
function copyText(){ 
  //inputTag라는 변수에 담긴 input 태그의 value(텍스트)를 클립보드에 쓰기
  navigator.clipboard.writeText(inputTag.value).then(res=>{
  	alert("Download Link Copied");
  })
}