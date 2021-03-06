/*
 * Copyright (c) 2018 ISP RAS (http://www.ispras.ru)
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

function set_actions_for_scheduler_user() {
    $('.for_popup').popup();
    function check_sch_u_data() {
        var err_found = false, login = $('#scheduler_login'),
            password = $('#scheduler_password'),
            password_retype = $('#scheduler_password_retype'),
            confirm = $('#add_new_sch_u');
        if (login.val().length == 0) {
            err_found = true;
            $('#sch_u_login_warn').show();
            login.parent().addClass('error');
        }
        else {
            $('#sch_u_login_warn').hide();
            login.parent().removeClass('error');
        }
        if (password.val().length == 0) {
            err_found = true;
            $('#sch_u_password_warn').show();
            password.parent().addClass('error');
        }
        else {
            $('#sch_u_password_warn').hide();
            password.parent().removeClass('error');
        }
        if (password_retype.val().length == 0) {
            err_found = true;
            $('#sch_u_password_retype_warn').show();
            password_retype.parent().addClass('error');
        }
        else {
            $('#sch_u_password_retype_warn').hide();
            password_retype.parent().removeClass('error');
        }
        if (password.val().length > 0 && password_retype.val().length > 0 && password_retype.val() != password.val()) {
            err_found = true;
            $('#sch_u_password_retype_warn_2').show();
            password_retype.parent().addClass('error');
        }
        else {
            $('#sch_u_password_retype_warn_2').hide();
            password_retype.parent().removeClass('error');
        }
        if (err_found) {
            if (!confirm.hasClass('disabled')) {
                confirm.addClass('disabled');
            }
        }
        else {
            confirm.removeClass('disabled');
        }
        return err_found;
    }
    $('#scheduler_login').on('input', function () {
        check_sch_u_data();
    });
    $('#scheduler_password').on('input', function () {
        check_sch_u_data();
    });
    $('#scheduler_password_retype').on('input', function () {
        check_sch_u_data();
    });
    $('#add_new_sch_u').click(function () {
        $.ajax({
            url: '/service/ajax/add_scheduler_user/',
            data: {
                login: $("#scheduler_login").val(),
                password: $("#scheduler_password").val()
            },
            type: 'POST',
            success: function (data) {
                if (data.error) {
                    err_notify(data.error);
                }
                else {
                    success_notify($('#sch_u_saved').text(), 10000);
                    $('#new_sch_u').remove();
                    $('.need-auth').show();
                }
            }
        });
    });
}


$(document).ready(function () {
    $('.note-popup').popup();

    function collect_parallelism() {
        var parallelism_values = [];
        $('.parallelism-values').each(function () { parallelism_values.push($(this).val()) });
        return parallelism_values;
    }

    function collect_boolean() {
        var bool_values = [];
        $('.boolean-value').each(function () { bool_values.push($(this).is(':checked')) });
        return bool_values;
    }

    function collect_data() {
        return {
            mode: 'data',
            data: JSON.stringify([
                [
                    $('input[name="priority"]:checked').val(),
                    $('input[name="scheduler"]:checked').val(),
                    parseInt($('#max_tasks').val()),
                    $('input[name=job_weight]:checked').val()
                ],
                collect_parallelism(),
                [
                    parseFloat($('#max_ram').val().replace(/,/, '.')),
                    parseInt($('#max_cpus').val()),
                    parseFloat($('#max_disk').val().replace(/,/, '.')),
                    $('#cpu_model').val()
                ],
                [
                    $('#console_logging_level').val(),
                    $('#console_log_formatter__value').val(),
                    $('#file_logging_level').val(),
                    $('#file_log_formatter__value').val()
                ],
                collect_boolean()
            ])
        }
    }
    $('#default_configs').dropdown({
        onChange: function () {
            var conf_name = $('#default_configs').val();
            if (conf_name == 'file_conf') {
                $('#upload_file_conf_form').show();
            }
            else {
                $.redirectPost('', {conf_name: conf_name});
            }
        }
    });
    $('#configuration_file_input').on('fileselect', function () {
        $('#upload_file_conf_form').submit();
    });

    $('.normal-dropdown').dropdown();
    $('.ui.scheduler-checkbox').addClass('checkbox');
    $('.scheduler-checkbox').checkbox({onChecked: function () {
        var new_sch_u = $('#new_sch_u');
        if (new_sch_u.length) {
            if ($(this).val() == '1') {
                new_sch_u.show();
                $('.need-auth').hide();
            }
            else {
                new_sch_u.hide();
                $('.need-auth').show();
            }
        }
    }});
    set_actions_for_scheduler_user();
    $('#start_job_decision').click(function () {

        var required_fields = [
            'max_tasks', 'max_ram', 'max_cpus', 'max_disk',
            'console_log_formatter__value', 'file_log_formatter__value',
            'sub_jobs_proc_parallelism__value', 'tasks_gen_parallelism__value',
            'results_processing_parallelism__value'
        ], err_found = false, numeric_fields = [
            'max_tasks', 'sub_jobs_proc_parallelism__value', 'tasks_gen_parallelism__value',
            'results_processing_parallelism__value',
            'max_ram', 'max_cpus', 'max_disk'
        ];
        $.each(required_fields, function (i, v) {
            var curr_input = $('#' + v);
            curr_input.parent().removeClass('error');
            if (!curr_input.val()) {
                curr_input.parent().addClass('error');
                err_found = true;
            }
        });
        if (err_found) {
            err_notify($('#fields_required').text());
            return false;
        }

        $.each(numeric_fields, function (i, v) {
            var curr_input = $('#' + v);
            curr_input.parent().removeClass('error');
            if (curr_input.val() && !$.isNumeric(curr_input.val()) && (curr_input.val().match(/^\s*\d+(,|\.)\d+\s*$/i) == null)) {
                curr_input.parent().addClass('error');
                err_found = true;
            }
        });

        if (err_found) {
            err_notify($('#numeric_required').text());
            return false;
        }
        $.ajax({
            url: '/jobs/run_decision/' + $('#job_pk').val() + '/',
            data: collect_data(),
            type: 'POST',
            success: function (data) {
                if (data.error) {
                    err_notify(data.error);
                }
                else {
                    window.location.replace($('#job_link').attr('href'));
                }
            }
        });
    });

    $('.get-attr-value').click(function () {
        $(this).find('input').each(function () {
            var attr_input = $(this);
            $.ajax({
                url: '/jobs/get_def_start_job_val/',
                data: {
                    name: attr_input.attr('name'),
                    value: attr_input.val()
                },
                type: 'POST',
                success: function (data) {
                    if (data.error) {
                        err_notify(data.error);
                        return false;
                    }
                    Object.keys(data).forEach(function(key) {
                        $('#' + key + '__value').val(data[key]);
                    });
                }
            });
        });
    });
});
