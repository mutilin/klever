/*
 * Klever-CV is a web-interface for continuous verification results visualization.
 *
 * Copyright (c) 2018-2019 ISP RAS (http://www.ispras.ru)
 * Ivannikov Institute for System Programming of the Russian Academy of Sciences
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * ee the License for the specific language governing permissions and
 * limitations under the License.
 */

$(document).ready(function () {
    $('#launch_button').click(function () {
        var data = new FormData();
        var files = $('#upload_witness')[0].files;
        if (!files.length) {
            err_notify($('#trans__err_witness').text());
            return;
        } else {
            data.append('upload_witness', files[0]);
        }
        var files = $('#upload_sources')[0].files;
        if (!files.length) {
            err_notify($('#trans__err_sources').text());
            return;
        } else {
            data.append('upload_sources', files[0]);
        }

        $(this).addClass('disabled');
        $.ajax({
            url: '/service/ajax/visualize_witness/',
            data: data,
            type: 'POST',
            dataType: 'json',
            contentType: false,
            processData: false,
            mimeType: 'multipart/form-data',
            xhr: function() {
                return $.ajaxSettings.xhr();
            },
            success: function (data) {
                if (data.error) {
                    err_notify(data.error);
                    $('#launch_button').removeClass('disabled');
                }
                else {
                    if (data.id) {
                        window.location.href = '/service/witness_visualizer/' + data.id;
                    } else {
                        err_notify("Cannot get visualized witness id");
                        $('#launch_button').removeClass('disabled');
                    }
                }
            }
        });
    });

    $('#upload_witness').on('fileselect', function () {
        $('#upload_witness_name').text($(this)[0].files[0].name);
        $('#upload_witness_button').removeClass("orange");
        $('#upload_witness_button').addClass("green");
    });
    $('#upload_sources').on('fileselect', function () {
        $('#upload_sources_name').text($(this)[0].files[0].name);
        $('#upload_sources_button').removeClass("orange");
        $('#upload_sources_button').addClass("green");
    });
});
