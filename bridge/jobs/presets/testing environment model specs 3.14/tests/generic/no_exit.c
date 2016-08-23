/*
 * Copyright (c) 2014-2016 ISPRAS (http://www.ispras.ru)
 * Institute for System Programming of the Russian Academy of Sciences
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

#include <linux/module.h>
#include <verifier/nondet.h>
#include <linux/emg/test_model.h>
#include "ldvops.h"

void ldv_handler(struct ldv_resource *arg)
{
    ldv_invoke_reached();
}

static struct ldv_driver ops = {
    .handler = ldv_handler,
};

static int __init ldv_init(void)
{
    return ldv_driver_register(& ops);
}

module_init(ldv_init);
