const getResp = function() {

    //user input
    var requestData = document.getElementById("textInput").value;
    var targetDropdown = document.getElementById("targetLanguageCodeDropdown");
    var destLang = targetDropdown.options[targetDropdown.selectedIndex].value;
    var voiceDropdown = document.getElementById("speechVoice");
    var speechVoice = voiceDropdown.options[voiceDropdown.selectedIndex].value;
    var chartDropdown = document.getElementById("chartShown");
    var chartShown = chartDropdown.options[chartDropdown.selectedIndex].value;

    console.log(requestData);
    console.log(destLang);
    console.log(speechVoice);

    fetch('https://1pgr51udtc.execute-api.us-east-1.amazonaws.com/dev/final-project-sentiment',{
        method: 'POST',
        body: JSON.stringify({text: requestData, dest_lang: destLang, voice: speechVoice}),
        headers: {
            'Content-type': 'application/json; charset=UTF-8'
        }
    }).then(function(response){
        console.log(response);
        //alert(response);
        return response.json();
    }).then(function(data){
        console.log(data.body);
        var outputRes = data.body;
        console.log(data.translated_text);
        var translated_text = data.translated_text;
        console.log(data.url_post);
        var url = data.url_post;

        //Extracting different sentiments from object
        var positiveSent = outputRes.Positive * 100;
        console.log(positiveSent);
        var negativeSent = outputRes.Negative * 100;
        var neutralSent = outputRes.Neutral * 100;
        var mixedSent = outputRes.Mixed * 100;
        var currElem = document.getElementById("sentButton");
        var player = "<audio controls><source src='" + url + "' type='audio/mpeg'></audio>"
        var newElem = `<br><h2 style = "text-align: center; color: #404040;" id = "sentLine">Result</h2><p style = "text-align: center; color: #404040; font-size: 16px">Translated Text in ${getLanguage(destLang)}: ${translated_text}</p>${player}`;
        currElem.insertAdjacentHTML('afterend', newElem);
        //calling sentiment plotting function
        plotSentiment(positiveSent, negativeSent, neutralSent, mixedSent, chartShown);
    }).catch(function(error) {
        console.warn('Something went wrong', error);
    })
};

//For plotting sentiment values
function plotSentiment(posSent, negSent, neutSent, mixedSent, chartShown) {
    if(chartShown == "pie"){
        var data = [{
            values: [posSent,negSent,neutSent,mixedSent],
            labels: ['Positive Sentiment', 'Negative Sentiment', 'Neutral Sentiment', 'Mixed Sentiment'],
            type: 'pie'
        }];
    }
    else if(chartShown == "bar"){
        var data = [{
            x: ['Positive Sentiment', 'Negative Sentiment', 'Neutral Sentiment', 'Mixed Sentiment'],
            y: [posSent,negSent,neutSent,mixedSent],
            type: 'bar'
        }]
    }

    var layout = {
        height: 300,
        width: 400
    };
    Plotly.newPlot('myDiv', data, layout, align = "center");
};

function getLanguage(lang_code) {
    var lang = {
        "ar": "Arabic",
        "zh": "Chinese (Simplified)",
        "zh-TW": "Chinese (Traditional)",
        "nl": "Dutch",
        "en": "English",
        "fr": "French",
        "de": "German",
        "hi": "Hindi",
        "it": "Italian",
        "ja": "Japanese",
        "ko": "Korean",
        "no": "Norwegian",
        "pt": "Portuguese",
        "ru": "Russian",
        "es": "Spanish",
        "tr": "Turkish",
    };
    return lang[lang_code]
}