window.get_tags_values = function () {
    var selected_tags = [];
    $('#selected_tags').children('span').each(function () {
        selected_tags.push($(this).text());
    });
    return selected_tags;
};

window.drow_connections = function () {
    $('.tagsmap').find(".line").each(function () {
        var for_style = [];
        $.each($(this).attr('class').split(/\s+/), function (a, cl_name) {
            var img_types;
            if (cl_name.startsWith('line-')) {
                 img_types = cl_name.replace('line-', '').split('');
            }
            if (img_types) {
                $.each(img_types, function (a, img_t) {
                    for_style.push("url('/static/marks/css/images/L_" + img_t + ".png') center no-repeat");
                });
            }
        });
        if (for_style.length) {
            $(this).attr('style', "background: " + for_style.join(',') + ';');
        }
    });
};

window.init_popups = function () {
    $('td[id^="tag_id_"]').each(function () {
        var tag_id = $(this).attr('id').replace('tag_id_', ''), tag_popup = $('#tag_popup_' + tag_id);
        if (tag_popup.length) {
            $(this).popup({
                popup: tag_popup,
                hoverable: true,
                delay: {show: 100, hide: 300},
                variation: 'very wide'
            });
        }
    });
};

window.activate_tags = function () {
    drow_connections();
    init_popups();

    function update_tags(deleted) {
        $.ajax({
            url: '/marks/ajax/get_tags_data/',
            type: 'POST',
            data: {
                tag_type: $('#tags_type').val(),
                selected_tags: JSON.stringify(get_tags_values()),
                deleted: deleted
            },
            success: function (data) {
                if (data.error) {
                    err_notify(data.error);
                    return false;
                }
                $('#tags_tree').html(data['tree']);
                activate_tags();

                $('#selected_tags').empty();
                $.each(JSON.parse(data['selected']), function (i, value) {
                    $('#selected_tags').append($('<span>', {text: value}));
                });
                var tags_list = $('#tag_list');
                tags_list.empty();
                $.each(JSON.parse(data['available']), function (i, value) {
                    $('#tag_list').append($('<option>', {text: value[1], value: value[0]}));
                });
            }
        });
    }

    $('#tag_list').dropdown({
        useLabels: false,
        className: {
            label: 'ui label ' + $('#tag_label_color').text()
        },
        message: {
            noResults: $('#error__no_results').text(),
            count: ''
        },
        onChange: function () {
            $(this).dropdown('hide');
            $('#selected_tags').append($('<span>', {text: $('#tag_list').val()[0]}));
            update_tags();
        }
    });
    $('i[id^="remove_tag_"]').click(function () {
        update_tags($(this).attr('id').replace('remove_tag_', ''));
    });
};